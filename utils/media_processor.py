import os
import json
from moviepy import VideoFileClip, AudioFileClip
from datetime import timedelta

class MediaProcessor:
    @staticmethod
    def get_media_info(filepath):
        """Extract media file information"""
        try:
            clip = VideoFileClip(filepath)
            duration = float(clip.duration)
            fps = float(clip.fps) if hasattr(clip, 'fps') else 0
            width, height = clip.size if hasattr(clip, 'size') else (0, 0)
            
            info = {
                'duration': duration,
                'duration_formatted': str(timedelta(seconds=int(duration))),
                'fps': round(fps, 2),
                'width': width,
                'height': height,
                'has_video': True,
                'has_audio': clip.audio is not None,
                'filename': os.path.basename(filepath),
                'size_mb': round(os.path.getsize(filepath) / (1024 * 1024), 2)
            }
            clip.close()
            return info
        except:
            # Try as audio file
            try:
                clip = AudioFileClip(filepath)
                duration = float(clip.duration)
                info = {
                    'duration': duration,
                    'duration_formatted': str(timedelta(seconds=int(duration))),
                    'fps': 0,
                    'width': 0,
                    'height': 0,
                    'has_video': False,
                    'has_audio': True,
                    'filename': os.path.basename(filepath),
                    'size_mb': round(os.path.getsize(filepath) / (1024 * 1024), 2)
                }
                clip.close()
                return info
            except Exception as e:
                return {'error': str(e)}
    
    @staticmethod
    def cut_media(filepath, start_time, end_time, output_format='mp4', quality='high'):
        """Cut media file and export"""
        try:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'outputs')
            os.makedirs(output_dir, exist_ok=True)
            
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            output_filename = f"{base_name}_cut_{start_time}_{end_time}.{output_format}"
            output_path = os.path.join(output_dir, output_filename)
            
            # Quality settings
            quality_settings = {
                'high': {'video_bitrate': '5000k', 'audio_bitrate': '320k'},
                'medium': {'video_bitrate': '2500k', 'audio_bitrate': '192k'},
                'low': {'video_bitrate': '1000k', 'audio_bitrate': '128k'}
            }
            
            settings = quality_settings.get(quality, quality_settings['high'])
            
            try:
                # Try as video first
                clip = VideoFileClip(filepath)
                is_video = True
            except:
                # Fall back to audio
                clip = AudioFileClip(filepath)
                is_video = False
            
            # Cut the clip
            cut_clip = clip.subclipped(start_time, end_time)
            
            # Export based on type
            if is_video and output_format in ['mp4', 'avi', 'mov', 'webm']:
                cut_clip.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    bitrate=settings['video_bitrate'],
                    audio_bitrate=settings['audio_bitrate'],
                    preset='medium'
                )
            elif not is_video or output_format in ['mp3', 'wav', 'ogg', 'm4a']:
                # Export as audio
                if output_format == 'mp3':
                    cut_clip.audio.write_audiofile(output_path, bitrate=settings['audio_bitrate'])
                else:
                    cut_clip.audio.write_audiofile(output_path)
            
            clip.close()
            cut_clip.close()
            
            return {
                'success': True,
                'output_path': output_path,
                'filename': output_filename
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
