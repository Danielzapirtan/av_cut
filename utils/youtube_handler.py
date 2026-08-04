import yt_dlp
import os
from config import Config

class YouTubeHandler:
    @staticmethod
    def download_video(url, output_dir=None):
        """Download YouTube video"""
        if output_dir is None:
            output_dir = Config.UPLOAD_FOLDER
            
        os.makedirs(output_dir, exist_ok=True)
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Get the actual filename (might be changed by postprocessor)
                if os.path.exists(filename):
                    final_path = filename
                else:
                    # Look for the converted file
                    base = os.path.splitext(filename)[0]
                    for ext in ['.mp4', '.webm', '.mkv']:
                        test_path = base + ext
                        if os.path.exists(test_path):
                            final_path = test_path
                            break
                    else:
                        raise Exception("Downloaded file not found")
                
                return {
                    'success': True,
                    'filepath': final_path,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'filename': os.path.basename(final_path)
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_video_info(url):
        """Get YouTube video information without downloading"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                formats = []
                for f in info.get('formats', []):
                    if f.get('ext') in ['mp4', 'webm'] and f.get('height'):
                        formats.append({
                            'format_id': f['format_id'],
                            'ext': f['ext'],
                            'resolution': f'{f.get("height")}p',
                            'filesize': f.get('filesize', 'Unknown')
                        })
                
                return {
                    'success': True,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'formats': formats[:10]  # Limit to top 10 formats
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
