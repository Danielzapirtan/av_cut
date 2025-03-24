import gradio as gr
import os
import yt_dlp
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip

UPLOAD_FOLDER = '/tmp/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'mp3', 'mp4'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_time(time_str):
    """Convert minutes:seconds format to seconds"""
    try:
        if ':' in time_str:
            minutes, seconds = map(float, time_str.split(':'))
            return minutes * 60 + seconds
        return float(time_str) * 60  # Backward compatibility for minutes-only input
    except ValueError:
        raise ValueError(f"Invalid time format: {time_str}. Please use minutes:seconds (e.g., 1:30)")

def get_duration(filepath):
    if filepath.endswith('.mp4'):
        clip = VideoFileClip(filepath)
    else:
        clip = AudioFileClip(filepath)

    duration = clip.duration
    clip.close()  # Ensure resource cleanup
    return duration

def cut_media(input_path, output_path, start_time, end_time=None):
    if input_path.endswith('.mp4'):
        with VideoFileClip(input_path) as video:
            if end_time is None:
                end_time = video.duration
            cut_video = video.subclip(start_time, end_time)
            cut_video.write_videofile(output_path, codec="libx264", audio_codec="aac")
    else:
        with AudioFileClip(input_path) as audio:
            if end_time is None:
                end_time = audio.duration
            cut_audio = audio.subclip(start_time, end_time)
            cut_audio.write_audiofile(output_path)

def download_from_url(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(UPLOAD_FOLDER, '%(title)s.%(ext)s'),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

def process_media(file, url, start_time_str, end_time_str=None, use_end=False):
    try:
        start_time = parse_time(start_time_str)
        end_time = parse_time(end_time_str) if end_time_str and not use_end else None

        if url:
            input_path = download_from_url(url)
        elif file:
            if not allowed_file(file.name):
                raise ValueError("Invalid file type. Only MP3 and MP4 files are allowed.")
            input_path = file.name
        else:
            raise ValueError("No file or URL provided")

        output_filename = f'cut_{os.path.basename(input_path)}'
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        cut_media(input_path, output_path, start_time, end_time)

        return output_path

    except Exception as e:
        return f"Error processing file: {str(e)}"

iface = gr.Interface(
    fn=process_media,
    inputs=[
        gr.File(label="Upload File"),
        gr.Textbox(label="YouTube URL"),
        gr.Textbox(label="Start Time (e.g., 1:30)", value="0:00"),
        gr.Textbox(label="End Time (e.g., 2:00)"),
        gr.Checkbox(label="Use end of file", value=False)
    ],
    outputs=gr.File(label="Download Cut Media"),
    title="Media Cutter",
    description="Upload a file or provide a YouTube URL to cut a segment from the media."
)

if __name__ == "__main__":
    iface.launch(share=True)