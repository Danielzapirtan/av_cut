import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max upload
    ALLOWED_EXTENSIONS = {
        'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'wmv',
        'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'wma'
    }
    YT_DLP_OPTIONS = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(UPLOAD_FOLDER, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }
