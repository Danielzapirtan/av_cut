from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
import os
import yt_dlp
from moviepy import VideoFileClip, AudioFileClip
import tempfile

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for flash messages
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp3', 'mp4'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_duration(filepath):
    if filepath.endswith('.mp4'):
        with VideoFileClip(filepath) as clip:
            return clip.duration
    else:
        with AudioFileClip(filepath) as clip:
            return clip.duration

def cut_media(input_path, output_path, start_time, end_time=None):
    if input_path.endswith('.mp4'):
        with VideoFileClip(input_path) as video:
            if end_time is None:
                end_time = video.duration
            cut_video = video.subclip(start_time, end_time)
            cut_video.write_videofile(output_path)
    else:
        with AudioFileClip(input_path) as audio:
            if end_time is None:
                end_time = audio.duration
            cut_audio = audio.subclip(start_time, end_time)
            cut_audio.write_audiofile(output_path)

def download_from_url(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(app.config['UPLOAD_FOLDER'], '%(title)s.%(ext)s'),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    return filename

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        start_minutes = float(request.form.get('start_minutes', 0))
        start_time = start_minutes * 60

        use_end = 'use_end' in request.form
        if not use_end:
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
            # Create output filename
            output_filename = f'cut_{os.path.basename(input_path)}'
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

            # Cut the media file
            cut_media(input_path, output_path, start_time, end_time)

            # Clean up input file
            if os.path.exists(input_path):
                os.remove(input_path)

            # Send the file to user and clean up
            response = send_file(output_path, as_attachment=True)
            os.remove(output_path)
            return response

        except Exception as e:
            flash(f'Error processing file: {str(e)}')
            return redirect(url_for('index'))

    return render_template('index.html')

if __name__== '__main__':
	app.run(debug=True)
