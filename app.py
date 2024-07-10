from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
import os
from moviepy.editor import VideoFileClip, ImageClip, concatenate_videoclips, CompositeVideoClip, TextClip
import openai
from flask_session import Session
import moviepy.video.fx.all as vfx

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# OpenAI APIキーを設定
# OpenAI APIキーを設定（環境変数から取得）
openai.api_key = os.getenv('OPENAI_API_KEY')

# ImageMagickのパスを設定
os.environ["IMAGEMAGICK_BINARY"] = "/usr/local/bin/convert"  # `which convert`で得られたパスを使用
# os.environ["IMAGEMAGICK_BINARY"] = "C:\\Program Files\\ImageMagick-7.0.10-Q16\\convert.exe"  # Windowsの例

# Jinja2でzipを使用できるようにカスタムフィルタを追加
@app.template_filter('zip')
def zip_filter(a, b):
    return zip(a, b)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({"message": "No files part"})
    files = request.files.getlist('files')
    file_paths = []
    for file in files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        file_paths.append(file_path)
    try:
        comments = generate_comments(file_paths)
        session['file_paths'] = file_paths
        session['comments'] = comments
        return render_template('edit.html', file_paths=file_paths, comments=comments)
    except openai.error.RateLimitError:
        return jsonify({"error": "API rate limit exceeded. Please try again later."}), 429
    except openai.error.AuthenticationError:
        return jsonify({"error": "Authentication error. Please check your API key."}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def generate_comments(file_paths):
    comments = []
    for file_path in file_paths:
        prompt = f"Generate a creative comment for this file: {file_path}"
        try:
            # response = openai.ChatCompletion.create(
            #     model="gpt-3.5-turbo",
            #     messages=[
            #         {"role": "system", "content": "You are a helpful assistant."},
            #         {"role": "user", "content": prompt}
            #     ]
            # )
            # comments.append(response['choices'][0]['message']['content'].strip())
            comments.append('test test test test test test test test')
        except Exception as e:
            comments.append(f"Error generating comment: {e}")
    # comments =['test']
    return comments

@app.route('/process', methods=['POST'])
def process_files():
    files = request.form.getlist('file_paths')
    comments = request.form.getlist('comments')
    if not files:
        return jsonify({"error": "No files provided"}), 400
    
    try:
        output_path = create_slideshow(files, comments)
        session['output_path'] = output_path
        return redirect(url_for('show_result'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def create_slideshow(file_paths, comments):
    clips = []
    for file, comment in zip(file_paths, comments):
        print(f"Processing file: {file}")  # デバッグ用出力
        try:
            if file.lower().endswith(('.mp4', '.mov')):
                clip = VideoFileClip(file).fx(vfx.fadein, 1).fx(vfx.fadeout, 1)
            elif file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                clip = ImageClip(file).set_duration(2).fx(vfx.fadein, 1).fx(vfx.fadeout, 1)
            else:
                print(f"Skipping unsupported file: {file}")
                continue
            
            # テキストクリップの作成
            txt_clip = TextClip(comment, fontsize=40, color='white', bg_color='black', method='caption').set_position(('center', 'bottom')).set_duration(clip.duration)
            print(f"Generated text clip for comment: {comment}")

            # クリップの合成
            video = CompositeVideoClip([clip, txt_clip])
            clips.append(video)
        except Exception as e:
            print(f"Error processing file {file}: {e}")
    
    if not clips:
        raise ValueError("No valid media clips found to create slideshow.")
    
    final_clip = concatenate_videoclips(clips, method="compose")
    output_path = os.path.join(app.config['PROCESSED_FOLDER'], 'slideshow.mp4')
    final_clip.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')
    return output_path

@app.route('/result')
def show_result():
    output_path = session.get('output_path', None)
    comments = session.get('comments', [])
    if not output_path:
        return redirect(url_for('index'))
    return render_template('result.html', output_path=output_path, comments=comments)

@app.route('/video/<filename>')
def video(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename)

# アップロードされた画像を表示するルートを追加
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
