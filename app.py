from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
import os
import yt_dlp
from moviepy import VideoFileClip, AudioFileClip

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
ALLOWED_EXTENSIONS = {'mp3', 'mp4'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cut_media(input_path, output_path, start_time, end_time=None):
    try:
        if input_path.lower().endswith('.mp4'):
            with VideoFileClip(input_path) as video:
                if end_time is None:
                    end_time = video.duration
                if start_time >= end_time:
                    raise ValueError("Start time must be less than end time.")
                cut_video = video.subclip(start_time, end_time)
                cut_video.write_videofile(output_path)
        else:
            with AudioFileClip(input_path) as audio:
                if end_time is None:
                    end_time = audio.duration
                if start_time >= end_time:
                    raise ValueError("Start time must be less than end time.")
                cut_audio = audio.subclip(start_time, end_time)
                cut_audio.write_audiofile(output_path)
    except Exception as e:
        raise e

def download_from_url(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(app.config['UPLOAD_FOLDER'], '%(title)s.%(ext)s'),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
        except Exception as e:
            raise e

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        start_minutes = float(request.form.get('start_minutes', 0))
        start_time = start_minutes * 60

        use_end = 'use_end' in request.form
        if use_end:
            end_minutes = float(request.form.get('end_minutes', 0))
            end_time = end_minutes * 60
        else:
            end_time = None

        # Handle URL input
        if url := request.form.get('url'):
            try:
                input_path = download_from_url(url)
            except Exception as e:
                flash(f'Error downloading from URL: {str(e)}')
                return redirect(url_for('index'))
        
        # Handle file upload
        elif 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                flash('No file selected')
                return redirect(url_for('index'))
            
            if not allowed_file(file.filename):
                flash('Invalid file type. Only MP3 and MP4 files are allowed.')
                return redirect(url_for('index'))
            
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
            file.save(input_path)
        else:
            flash('No file or URL provided')
            return redirect(url_for('index'))

        try:
            output_filename = f'cut_{os.path.basename(input_path)}'
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            cut_media(input_path, output_path, start_time, end_time)
            
            if os.path.exists(input_path):
                os.remove(input_path)

            response = send_file(output_path, as_attachment=True)
            os.remove(output_path)
            return response

        except Exception as e:
            flash(f'Error processing file: {str(e)}')
            if os.path.exists(input_path):
                os.remove(input_path)
            return redirect(url_for('index'))

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)