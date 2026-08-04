#!/usr/bin/env python3
"""
Audio/Video Cutter Flask App
Accepts audio/video files, YouTube URLs, provides preview, editing with timers/handles,
and allows playing/downloading in various formats and qualities.
"""

import os
import uuid
import json
import subprocess
import threading
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, Response
import yt_dlp
import tempfile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

UPLOAD_FOLDER = Path(tempfile.gettempdir()) / 'media_cutter'
UPLOAD_FOLDER.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {
    'video': {'mp4', 'avi', 'mkv', 'mov', 'webm', 'flv', 'wmv', 'm4v', 'mpeg', 'mpg'},
    'audio': {'mp3', 'wav', 'aac', 'flac', 'ogg', 'm4a', 'wma', 'opus'}
}

def allowed_file(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in ALLOWED_EXTENSIONS['video'] | ALLOWED_EXTENSIONS['audio']

def get_media_info(filepath):
    """Get media duration and type using ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_streams', '-show_format', str(filepath)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        duration = float(data.get('format', {}).get('duration', 0))
        
        has_video = any(s.get('codec_type') == 'video' for s in data.get('streams', []))
        has_audio = any(s.get('codec_type') == 'audio' for s in data.get('streams', []))
        
        video_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
        width = video_stream.get('width', 0) if video_stream else 0
        height = video_stream.get('height', 0) if video_stream else 0
        
        return {
            'duration': duration,
            'has_video': has_video,
            'has_audio': has_audio,
            'width': width,
            'height': height
        }
    except Exception as e:
        return {'duration': 0, 'has_video': False, 'has_audio': True, 'width': 0, 'height': 0}

def download_youtube(url, session_id):
    """Download YouTube video using yt-dlp."""
    output_dir = UPLOAD_FOLDER / session_id
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / 'source.%(ext)s'
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': str(output_path),
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'video')
    
    # Find the downloaded file
    for f in output_dir.iterdir():
        if f.stem == 'source':
            return f, title
    
    return None, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    session_id = str(uuid.uuid4())
    output_dir = UPLOAD_FOLDER / session_id
    output_dir.mkdir(exist_ok=True)
    
    try:
        if 'youtube_url' in request.form and request.form['youtube_url']:
            url = request.form['youtube_url'].strip()
            filepath, title = download_youtube(url, session_id)
            if not filepath:
                return jsonify({'error': 'Failed to download YouTube video'}), 400
            filename = filepath.name
            media_type = 'video'
        
        elif 'file' in request.files:
            file = request.files['file']
            if not file or not file.filename:
                return jsonify({'error': 'No file provided'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'error': 'File type not allowed'}), 400
            
            filename = file.filename
            ext = filename.rsplit('.', 1)[1].lower()
            filepath = output_dir / f'source.{ext}'
            file.save(filepath)
            
            media_type = 'video' if ext in ALLOWED_EXTENSIONS['video'] else 'audio'
        
        else:
            return jsonify({'error': 'No file or URL provided'}), 400
        
        # Get media info
        info = get_media_info(filepath)
        info['session_id'] = session_id
        info['filename'] = filename
        info['media_type'] = 'video' if info['has_video'] else 'audio'
        
        return jsonify(info)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/preview/<session_id>')
def preview(session_id):
    """Stream the source media for preview."""
    session_dir = UPLOAD_FOLDER / session_id
    
    source_file = None
    for f in session_dir.iterdir():
        if f.stem == 'source':
            source_file = f
            break
    
    if not source_file:
        return jsonify({'error': 'Source file not found'}), 404
    
    ext = source_file.suffix.lower()
    
    mime_types = {
        '.mp4': 'video/mp4', '.webm': 'video/webm', '.mkv': 'video/x-matroska',
        '.avi': 'video/x-msvideo', '.mov': 'video/quicktime',
        '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg',
        '.aac': 'audio/aac', '.flac': 'audio/flac', '.m4a': 'audio/mp4',
        '.m4v': 'video/mp4', '.flv': 'video/x-flv', '.wmv': 'video/x-ms-wmv',
        '.mpeg': 'video/mpeg', '.mpg': 'video/mpeg', '.opus': 'audio/ogg',
    }
    mime = mime_types.get(ext, 'application/octet-stream')
    
    file_size = source_file.stat().st_size
    range_header = request.headers.get('Range')
    
    if range_header:
        byte_start, byte_end = 0, None
        match = range_header.replace('bytes=', '').split('-')
        byte_start = int(match[0])
        byte_end = int(match[1]) if match[1] else file_size - 1
        
        length = byte_end - byte_start + 1
        
        def generate():
            with open(source_file, 'rb') as f:
                f.seek(byte_start)
                remaining = length
                while remaining:
                    chunk = f.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        
        response = Response(generate(), 206, mimetype=mime,
                          content_type=mime, direct_passthrough=True)
        response.headers['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Length'] = length
        return response
    
    return send_file(source_file, mimetype=mime)

@app.route('/cut', methods=['POST'])
def cut_media():
    """Cut media and convert to specified format/quality."""
    data = request.json
    session_id = data.get('session_id')
    start_time = float(data.get('start', 0))
    end_time = float(data.get('end', 0))
    output_format = data.get('format', 'mp4')
    quality = data.get('quality', 'medium')
    action = data.get('action', 'download')  # 'download' or 'preview'
    
    session_dir = UPLOAD_FOLDER / session_id
    source_file = None
    for f in session_dir.iterdir():
        if f.stem == 'source':
            source_file = f
            break
    
    if not source_file:
        return jsonify({'error': 'Source file not found'}), 404
    
    output_filename = f'cut_{uuid.uuid4().hex[:8]}.{output_format}'
    output_path = session_dir / output_filename
    
    duration = end_time - start_time
    
    # Quality presets
    quality_presets = {
        'video': {
            'high': ['-crf', '18', '-preset', 'slow'],
            'medium': ['-crf', '23', '-preset', 'medium'],
            'low': ['-crf', '28', '-preset', 'fast'],
        },
        'audio': {
            'high': '320k',
            'medium': '192k',
            'low': '128k',
        }
    }
    
    audio_formats = {'mp3', 'wav', 'aac', 'flac', 'ogg', 'm4a', 'opus'}
    is_audio_output = output_format in audio_formats
    
    cmd = ['ffmpeg', '-y', '-ss', str(start_time), '-i', str(source_file),
           '-t', str(duration)]
    
    if is_audio_output:
        if output_format == 'mp3':
            cmd.extend(['-vn', '-acodec', 'libmp3lame',
                       '-b:a', quality_presets['audio'][quality]])
        elif output_format == 'wav':
            cmd.extend(['-vn', '-acodec', 'pcm_s16le'])
        elif output_format == 'aac':
            cmd.extend(['-vn', '-acodec', 'aac',
                       '-b:a', quality_presets['audio'][quality]])
        elif output_format == 'flac':
            cmd.extend(['-vn', '-acodec', 'flac'])
        elif output_format == 'ogg':
            cmd.extend(['-vn', '-acodec', 'libvorbis',
                       '-b:a', quality_presets['audio'][quality]])
        elif output_format == 'm4a':
            cmd.extend(['-vn', '-acodec', 'aac',
                       '-b:a', quality_presets['audio'][quality]])
        elif output_format == 'opus':
            cmd.extend(['-vn', '-acodec', 'libopus',
                       '-b:a', quality_presets['audio'][quality]])
    else:
        if output_format == 'mp4':
            cmd.extend(['-vcodec', 'libx264', '-acodec', 'aac'])
            cmd.extend(quality_presets['video'][quality])
        elif output_format == 'webm':
            cmd.extend(['-vcodec', 'libvpx-vp9', '-acodec', 'libopus'])
            cmd.extend(['-crf', '33' if quality == 'low' else '23' if quality == 'medium' else '15'])
        elif output_format == 'mkv':
            cmd.extend(['-vcodec', 'libx264', '-acodec', 'aac'])
            cmd.extend(quality_presets['video'][quality])
        elif output_format == 'avi':
            cmd.extend(['-vcodec', 'libxvid', '-acodec', 'mp3'])
        elif output_format == 'mov':
            cmd.extend(['-vcodec', 'libx264', '-acodec', 'aac'])
            cmd.extend(quality_presets['video'][quality])
        elif output_format == 'gif':
            cmd.extend(['-vf', 'fps=10,scale=480:-1:flags=lanczos', '-loop', '0'])
    
    cmd.append(str(output_path))
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        return jsonify({'error': f'FFmpeg error: {result.stderr}'}), 500
    
    if action == 'preview':
        cut_id = output_filename.replace(f'.{output_format}', '')
        return jsonify({'cut_id': cut_id, 'filename': output_filename, 'session_id': session_id})
    
    mime_types = {
        'mp4': 'video/mp4', 'webm': 'video/webm', 'mkv': 'video/x-matroska',
        'avi': 'video/x-msvideo', 'mov': 'video/quicktime', 'gif': 'image/gif',
        'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'ogg': 'audio/ogg',
        'aac': 'audio/aac', 'flac': 'audio/flac', 'm4a': 'audio/mp4', 'opus': 'audio/ogg'
    }
    
    return send_file(
        output_path,
        mimetype=mime_types.get(output_format, 'application/octet-stream'),
        as_attachment=True,
        download_name=output_filename
    )

@app.route('/download/<session_id>/<filename>')
def download_cut(session_id, filename):
    """Download a previously cut file."""
    filepath = UPLOAD_FOLDER / session_id / filename
    if not filepath.exists():
        return jsonify({'error': 'File not found'}), 404
    
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    mime_types = {
        'mp4': 'video/mp4', 'webm': 'video/webm', 'mkv': 'video/x-matroska',
        'avi': 'video/x-msvideo', 'mov': 'video/quicktime', 'gif': 'image/gif',
        'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'ogg': 'audio/ogg',
        'aac': 'audio/aac', 'flac': 'audio/flac', 'm4a': 'audio/mp4', 'opus': 'audio/ogg'
    }
    
    return send_file(
        filepath,
        mimetype=mime_types.get(ext, 'application/octet-stream'),
        as_attachment=True,
        download_name=filename
    )

@app.route('/stream_cut/<session_id>/<filename>')
def stream_cut(session_id, filename):
    """Stream a cut file for in-browser preview."""
    filepath = UPLOAD_FOLDER / session_id / filename
    if not filepath.exists():
        return jsonify({'error': 'File not found'}), 404
    
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    mime_types = {
        'mp4': 'video/mp4', 'webm': 'video/webm',
        'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'ogg': 'audio/ogg',
        'aac': 'audio/aac', 'm4a': 'audio/mp4', 'opus': 'audio/ogg'
    }
    mime = mime_types.get(ext, 'application/octet-stream')
    
    file_size = filepath.stat().st_size
    range_header = request.headers.get('Range')
    
    if range_header:
        byte_start, byte_end = 0, None
        match = range_header.replace('bytes=', '').split('-')
        byte_start = int(match[0])
        byte_end = int(match[1]) if match[1] else file_size - 1
        length = byte_end - byte_start + 1
        
        def generate():
            with open(filepath, 'rb') as f:
                f.seek(byte_start)
                remaining = length
                while remaining:
                    chunk = f.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        
        response = Response(generate(), 206, mimetype=mime, direct_passthrough=True)
        response.headers['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Length'] = length
        return response
    
    return send_file(filepath, mimetype=mime)

@app.route('/cleanup/<session_id>', methods=['DELETE'])
def cleanup(session_id):
    """Clean up session files."""
    import shutil
    session_dir = UPLOAD_FOLDER / session_id
    if session_dir.exists():
        shutil.rmtree(session_dir)
    return jsonify({'status': 'ok'})

# Create templates directory
templates_dir = Path('templates')
templates_dir.mkdir(exist_ok=True)

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Media Cutter</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; }
.app { max-width: 900px; margin: 0 auto; padding: 20px; }
h1 { text-align: center; color: #e94560; margin-bottom: 30px; font-size: 2rem; }
h1 span { color: #0f3460; }

.card { background: #16213e; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
.card h2 { color: #e94560; margin-bottom: 15px; font-size: 1.1rem; }

.upload-area { border: 2px dashed #0f3460; border-radius: 8px; padding: 30px; text-align: center; cursor: pointer; transition: all 0.3s; }
.upload-area:hover, .upload-area.drag-over { border-color: #e94560; background: rgba(233,69,96,0.05); }
.upload-area input { display: none; }
.upload-area p { color: #888; margin-top: 8px; font-size: 0.9rem; }

.url-row { display: flex; gap: 10px; margin-top: 15px; }
.url-row input { flex: 1; background: #0f3460; border: 1px solid #1a4a8a; color: #eee; padding: 10px 15px; border-radius: 8px; font-size: 0.95rem; }
.url-row input:focus { outline: none; border-color: #e94560; }

btn { display: inline-block; padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-size: 0.9rem; font-weight: 600; transition: all 0.2s; }
.btn-primary { background: #e94560; color: #fff; }
.btn-primary:hover { background: #c73652; }
.btn-secondary { background: #0f3460; color: #eee; }
.btn-secondary:hover { background: #1a4a8a; }
.btn-success { background: #27ae60; color: #fff; }
.btn-success:hover { background: #1e8449; }
.btn-info { background: #2980b9; color: #fff; }
.btn-info:hover { background: #1f6fa0; }
button { display: inline-block; padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-size: 0.9rem; font-weight: 600; transition: all 0.2s; }
.btn-primary { background: #e94560; color: #fff; }
.btn-primary:hover { background: #c73652; }

.progress-bar { width: 100%; height: 6px; background: #0f3460; border-radius: 3px; margin-top: 15px; display: none; }
.progress-bar .fill { height: 100%; background: #e94560; border-radius: 3px; width: 0; transition: width 0.3s; animation: indeterminate 1.5s infinite; }
@keyframes indeterminate { 0% { width: 0; margin-left: 0; } 50% { width: 60%; margin-left: 20%; } 100% { width: 0; margin-left: 100%; } }

#mediaSection { display: none; }

.media-container { position: relative; background: #000; border-radius: 8px; overflow: hidden; }
video, audio { width: 100%; display: block; }
audio { padding: 10px; background: #0f3460; }

/* Timeline */
.timeline-wrap { margin-top: 15px; position: relative; }
.waveform-container { position: relative; height: 70px; background: #0d1b3e; border-radius: 8px; overflow: hidden; cursor: pointer; }
canvas#waveform { width: 100%; height: 100%; display: block; }

.timeline { position: relative; height: 50px; background: #0d1b3e; border-radius: 8px; margin-top: 8px; user-select: none; }
.timeline-track { position: absolute; top: 15px; left: 0; right: 0; height: 20px; background: #1a4a8a; border-radius: 4px; }
.timeline-selection { position: absolute; top: 15px; height: 20px; background: rgba(233,69,96,0.4); border-top: 2px solid #e94560; border-bottom: 2px solid #e94560; pointer-events: none; }
.handle { position: absolute; top: 10px; width: 12px; height: 30px; background: #e94560; border-radius: 4px; cursor: ew-resize; transform: translateX(-50%); z-index: 10; }
.handle::after { content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); width: 2px; height: 16px; background: rgba(255,255,255,0.6); border-radius: 1px; }
.playhead { position: absolute; top: 5px; width: 2px; height: 40px; background: #fff; pointer-events: none; z-index: 5; }
.time-labels { display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.75rem; color: #888; }

/* Time inputs */
.time-inputs { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px; }
.time-group label { display: block; font-size: 0.8rem; color: #888; margin-bottom: 5px; }
.time-group input { width: 100%; background: #0f3460; border: 1px solid #1a4a8a; color: #eee; padding: 8px 12px; border-radius: 6px; font-size: 0.95rem; }
.time-group input:focus { outline: none; border-color: #e94560; }

/* Output options */
.options-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
.option-group label { display: block; font-size: 0.8rem; color: #888; margin-bottom: 5px; }
.option-group select { width: 100%; background: #0f3460; border: 1px solid #1a4a8a; color: #eee; padding: 8px 12px; border-radius: 6px; font-size: 0.95rem; }
.option-group select:focus { outline: none; border-color: #e94560; }

.action-row { display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap; }

/* Cut preview */
#cutPreview { display: none; margin-top: 15px; }
.cut-preview-label { font-size: 0.85rem; color: #888; margin-bottom: 8px; }

.status { padding: 10px 15px; border-radius: 6px; margin-top: 10px; font-size: 0.9rem; }
.status.error { background: rgba(233,69,96,0.2); color: #e94560; border: 1px solid rgba(233,69,96,0.3); }
.status.success { background: rgba(39,174,96,0.2); color: #27ae60; border: 1px solid rgba(39,174,96,0.3); }
.status.info { background: rgba(41,128,185,0.2); color: #2980b9; border: 1px solid rgba(41,128,185,0.3); }

.duration-badge { display: inline-block; background: #e94560; color: #fff; padding: 3px 10px; border-radius: 20px; font-size: 0.8rem; margin-left: 10px; }

@media (max-width: 600px) {
  .time-inputs, .options-grid { grid-template-columns: 1fr; }
  .action-row { flex-direction: column; }
  .action-row button { width: 100%; }
}
</style>
</head>
<body>
<div class="app">
  <h1>🎬 Media <span style="color:#e94560">Cutter</span></h1>

  <div class="card">
    <h2>📁 Load Media</h2>
    <div class="upload-area" id="uploadArea">
      <input type="file" id="fileInput" accept="video/*,audio/*">
      <div style="font-size:2rem">🎵</div>
      <strong>Drop file here or click to browse</strong>
      <p>Supports MP4, MKV, AVI, MOV, WebM, MP3, WAV, AAC, FLAC, OGG, M4A and more</p>
    </div>
    <div class="url-row">
      <input type="text" id="youtubeUrl" placeholder="Or paste YouTube URL...">
      <button class="btn-primary" onclick="loadYouTube()">▶ Load</button>
    </div>
    <div class="progress-bar" id="uploadProgress"><div class="fill"></div></div>
    <div id="uploadStatus"></div>
  </div>

  <div id="mediaSection">
    <div class="card">
      <h2>▶ Preview <span id="durationBadge" class="duration-badge"></span></h2>
      <div class="media-container">
        <video id="videoPlayer" controls preload="metadata" style="max-height:400px;display:none"></video>
        <audio id="audioPlayer" controls preload="metadata" style="display:none"></audio>
      </div>
      
      <div class="timeline-wrap">
        <div class="waveform-container" id="waveformContainer">
          <canvas id="waveform"></canvas>
        </div>
        
        <div class="timeline" id="timeline">
          <div class="timeline-track"></div>
          <div class="timeline-selection" id="selection"></div>
          <div class="handle" id="handleLeft"></div>
          <div class="handle" id="handleRight"></div>
          <div class="playhead" id="playhead"></div>
        </div>
        <div class="time-labels">
          <span id="timeStart">0:00</span>
          <span id="timeMid"></span>
          <span id="timeEnd">0:00</span>
        </div>
      </div>

      <div class="time-inputs">
        <div class="time-group">
          <label>Start Time</label>
          <input type="text" id="startInput" placeholder="0:00.000" oninput="handleTimeInput('start')">
        </div>
        <div class="time-group">
          <label>End Time</label>
          <input type="text" id="endInput" placeholder="0:00.000" oninput="handleTimeInput('end')">
        </div>
      </div>
    </div>

    <div class="card">
      <h2>⚙ Export Settings</h2>
      <div class="options-grid">
        <div class="option-group">
          <label>Output Format</label>
          <select id="outputFormat" onchange="updateFormatOptions()">
            <optgroup label="Video">
              <option value="mp4">MP4</option>
              <option value="webm">WebM</option>
              <option value="mkv">MKV</option>
              <option value="avi">AVI</option>
              <option value="mov">MOV</option>
              <option value="gif">GIF (animation)</option>
            </optgroup>
            <optgroup label="Audio">
              <option value="mp3">MP3</option>
              <option value="aac">AAC</option>
              <option value="wav">WAV (lossless)</option>
              <option value="flac">FLAC (lossless)</option>
              <option value="ogg">OGG Vorbis</option>
              <option value="m4a">M4A</option>
              <option value="opus">Opus</option>
            </optgroup>
          </select>
        </div>
        <div class="option-group" id="qualityGroup">
          <label>Quality</label>
          <select id="outputQuality">
            <option value="high">High</option>
            <option value="medium" selected>Medium</option>
            <option value="low">Low (smaller file)</option>
          </select>
        </div>
      </div>

      <div class="action-row">
        <button class="btn-primary" onclick="cutMedia('preview')" id="btnPreview">
          👁 Preview Cut
        </button>
        <button class="btn-success" onclick="cutMedia('download')" id="btnDownload">
          ⬇ Download Cut
        </button>
      </div>
      
      <div class="progress-bar" id="cutProgress"><div class="fill"></div></div>
      <div id="cutStatus"></div>

      <div id="cutPreview">
        <div class="cut-preview-label">Cut Preview:</div>
        <div class="media-container">
          <video id="cutVideo" controls style="display:none;max-height:300px"></video>
          <audio id="cutAudio" controls style="display:none"></audio>
        </div>
        <div style="margin-top:10px">
          <button class="btn-success" onclick="downloadFromPreview()" id="btnDownloadPreview">
            ⬇ Download This Cut
          </button>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
let sessionId = null;
let duration = 0;
let startTime = 0;
let endTime = 0;
let isDragging = null;
let mediaType = 'video';
let lastCutFile = null;
let lastCutFormat = null;

const timeline = document.getElementById('timeline');
const handleLeft = document.getElementById('handleLeft');
const handleRight = document.getElementById('handleRight');
const selection = document.getElementById('selection');
const playhead = document.getElementById('playhead');
const videoPlayer = document.getElementById('videoPlayer');
const audioPlayer = document.getElementById('audioPlayer');

function getPlayer() {
  return mediaType === 'video' ? videoPlayer : audioPlayer;
}

// Drag-and-drop upload
const uploadArea = document.getElementById('uploadArea');
uploadArea.addEventListener('click', () => document.getElementById('fileInput').click());
uploadArea.addEventListener('dragover', e => { e.preventDefault(); uploadArea.classList.add('drag-over'); });
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('drag-over'));
uploadArea.addEventListener('drop', e => {
  e.preventDefault();
  uploadArea.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});
document.getElementById('fileInput').addEventListener('change', e => {
  if (e.target.files[0]) uploadFile(e.target.files[0]);
});

async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  await doUpload(formData);
}

async function loadYouTube() {
  const url = document.getElementById('youtubeUrl').value.trim();
  if (!url) return;
  const formData = new FormData();
  formData.append('youtube_url', url);
  await doUpload(formData, 'Downloading from YouTube...');
}

async function doUpload(formData, loadingMsg = 'Uploading...') {
  showStatus('uploadStatus', loadingMsg, 'info');
  document.getElementById('uploadProgress').style.display = 'block';
  
  try {
    const resp = await fetch('/upload', { method: 'POST', body: formData });
    const data = await resp.json();
    document.getElementById('uploadProgress').style.display = 'none';
    
    if (data.error) {
      showStatus('uploadStatus', data.error, 'error');
      return;
    }
    
    sessionId = data.session_id;
    duration = data.duration;
    mediaType = data.has_video ? 'video' : 'audio';
    startTime = 0;
    endTime = duration;
    
    showStatus('uploadStatus', `Loaded: ${data.filename} (${formatTime(duration)})`, 'success');
    
    const previewUrl = `/preview/${sessionId}`;
    
    if (data.has_video) {
      videoPlayer.style.display = 'block';
      audioPlayer.style.display = 'none';
      videoPlayer.src = previewUrl;
    } else {
      audioPlayer.style.display = 'block';
      videoPlayer.style.display = 'none';
      audioPlayer.src = previewUrl;
    }
    
    document.getElementById('mediaSection').style.display = 'block';
    document.getElementById('durationBadge').textContent = formatTime(duration);
    document.getElementById('timeEnd').textContent = formatTime(duration);
    document.getElementById('timeMid').textContent = formatTime(duration / 2);
    
    updateHandles();
    updateInputs();
    
    // Draw simple waveform placeholder
    drawWaveformPlaceholder();
    
    // Set up player events
    const player = getPlayer();
    player.addEventListener('timeupdate', updatePlayhead);
    
    // Timeline click to seek
    timeline.addEventListener('click', seekOnClick);
    
    // Default format
    if (!data.has_video) {
      document.getElementById('outputFormat').value = 'mp3';
      updateFormatOptions();
    }
    
  } catch(e) {
    document.getElementById('uploadProgress').style.display = 'none';
    showStatus('uploadStatus', 'Upload failed: ' + e.message, 'error');
  }
}

function drawWaveformPlaceholder() {
  const canvas = document.getElementById('waveform');
  const container = document.getElementById('waveformContainer');
  canvas.width = container.offsetWidth;
  canvas.height = 70;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#0d1b3e';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  
  ctx.strokeStyle = '#e94560';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  const step = 4;
  for (let x = 0; x < canvas.width; x += step) {
    const h = (Math.random() * 0.6 + 0.1) * (canvas.height / 2);
    const cx = x + step / 2;
    ctx.moveTo(cx, canvas.height / 2 - h);
    ctx.lineTo(cx, canvas.height / 2 + h);
  }
  ctx.stroke();
  
  // Overlay for selected region
  canvas.onclick = function(e) {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const t = (x / canvas.width) * duration;
    const player = getPlayer();
    player.currentTime = t;
  };
}

function updatePlayhead() {
  const player = getPlayer();
  const pct = player.currentTime / duration;
  playhead.style.left = (pct * 100) + '%';
}

function seekOnClick(e) {
  if (isDragging) return;
  const rect = timeline.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const pct = Math.max(0, Math.min(1, x / rect.width));
  const t = pct * duration;
  getPlayer().currentTime = t;
}

// Handle dragging
function startDrag(e, handle) {
  e.preventDefault();
  isDragging = handle;
  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', stopDrag);
  document.addEventListener('touchmove', onDragTouch, {passive:false});
  document.addEventListener('touchend', stopDrag);
}

handleLeft.addEventListener('mousedown', e => startDrag(e, 'left'));
handleRight.addEventListener('mousedown', e => startDrag(e, 'right'));
handleLeft.addEventListener('touchstart', e => startDrag(e, 'left'), {passive:false});
handleRight.addEventListener('touchstart', e => startDrag(e, 'right'), {passive:false});

function getTimeFromEvent(e) {
  const rect = timeline.getBoundingClientRect();
  const clientX = e.touches ? e.touches[0].clientX : e.clientX;
  const x = clientX - rect.left;
  const pct = Math.max(0, Math.min(1, x / rect.width));
  return pct * duration;
}

function onDrag(e) {
  if (!isDragging) return;
  const t = getTimeFromEvent(e);
  if (isDragging === 'left') {
    startTime = Math.min(t, endTime - 0.1);
    startTime = Math.max(0, startTime);
  } else {
    endTime = Math.max(t, startTime + 0.1);
    endTime = Math.min(duration, endTime);
  }
  updateHandles();
  updateInputs();
}
function onDragTouch(e) { e.preventDefault(); onDrag(e); }

function stopDrag() {
  isDragging = null;
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
  document.removeEventListener('touchmove', onDragTouch);
  document.removeEventListener('touchend', stopDrag);
}

function updateHandles() {
  const leftPct = (startTime / duration) * 100;
  const rightPct = (endTime / duration) * 100;
  handleLeft.style.left = leftPct + '%';
  handleRight.style.left = rightPct + '%';
  selection.style.left = leftPct + '%';
  selection.style.width = (rightPct - leftPct) + '%';
}

function updateInputs() {
  document.getElementById('startInput').value = formatTime(startTime);
  document.getElementById('endInput').value = formatTime(endTime);
}

function handleTimeInput(which) {
  const val = which === 'start' ? document.getElementById('startInput').value 
                                : document.getElementById('endInput').value;
  const t = parseTime(val);
  if (isNaN(t)) return;
  
  if (which === 'start') {
    startTime = Math.max(0, Math.min(t, endTime - 0.1));
  } else {
    endTime = Math.min(duration, Math.max(t, startTime + 0.1));
  }
  updateHandles();
}

function parseTime(s) {
  // Supports: ss, mm:ss, hh:mm:ss, and decimal variants
  s = s.trim().replace(',', '.');
  const parts = s.split(':');
  if (parts.length === 1) return parseFloat(parts[0]);
  if (parts.length === 2) return parseInt(parts[0]) * 60 + parseFloat(parts[1]);
  return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseFloat(parts[2]);
}

function formatTime(s) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = (s % 60).toFixed(3);
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(6,'0')}`;
  return `${m}:${String(sec).padStart(6,'0')}`;
}

function updateFormatOptions() {
  const fmt = document.getElementById('outputFormat').value;
  const lossless = ['wav', 'flac'].includes(fmt);
  const gif = fmt === 'gif';
  const qGroup = document.getElementById('qualityGroup');
  qGroup.style.opacity = (lossless || gif) ? '0.4' : '1';
  if (lossless || gif) document.getElementById('outputQuality').disabled = true;
  else document.getElementById('outputQuality').disabled = false;
}

async function cutMedia(action) {
  if (!sessionId) return;
  
  const format = document.getElementById('outputFormat').value;
  const quality = document.getElementById('outputQuality').value;
  
  const progressEl = document.getElementById('cutProgress');
  progressEl.style.display = 'block';
  
  document.getElementById('btnPreview').disabled = true;
  document.getElementById('btnDownload').disabled = true;
  showStatus('cutStatus', 'Processing...', 'info');
  document.getElementById('cutPreview').style.display = 'none';
  
  try {
    const resp = await fetch('/cut', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        session_id: sessionId,
        start: startTime,
        end: endTime,
        format: format,
        quality: quality,
        action: action
      })
    });
    
    progressEl.style.display = 'none';
    
    if (action === 'download') {
      if (!resp.ok) {
        const err = await resp.json();
        showStatus('cutStatus', err.error || 'Processing failed', 'error');
      } else {
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cut.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        showStatus('cutStatus', 'Downloaded!', 'success');
      }
    } else {
      // preview
      const data = await resp.json();
      if (data.error) {
        showStatus('cutStatus', data.error, 'error');
      } else {
        lastCutFile = data.filename;
        lastCutFormat = format;
        
        const previewUrl = `/stream_cut/${sessionId}/${data.filename}`;
        const audioFmts = ['mp3','wav','aac','flac','ogg','m4a','opus'];
        const isAudio = audioFmts.includes(format);
        
        const cutVideo = document.getElementById('cutVideo');
        const cutAudio = document.getElementById('cutAudio');
        
        if (isAudio) {
          cutAudio.src = previewUrl;
          cutAudio.style.display = 'block';
          cutVideo.style.display = 'none';
        } else {
          cutVideo.src = previewUrl;
          cutVideo.style.display = 'block';
          cutAudio.style.display = 'none';
        }
        
        document.getElementById('cutPreview').style.display = 'block';
        showStatus('cutStatus', `Cut ready: ${formatTime(startTime)} → ${formatTime(endTime)} (${format.toUpperCase()})`, 'success');
      }
    }
  } catch(e) {
    progressEl.style.display = 'none';
    showStatus('cutStatus', 'Error: ' + e.message, 'error');
  }
  
  document.getElementById('btnPreview').disabled = false;
  document.getElementById('btnDownload').disabled = false;
}

async function downloadFromPreview() {
  if (!lastCutFile || !sessionId) return;
  window.location.href = `/download/${sessionId}/${lastCutFile}`;
}

function showStatus(id, msg, type) {
  const el = document.getElementById(id);
  el.innerHTML = `<div class="status ${type}">${msg}</div>`;
}

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (!sessionId) return;
  const player = getPlayer();
  if (e.code === 'Space' && !['INPUT','TEXTAREA'].includes(e.target.tagName)) {
    e.preventDefault();
    player.paused ? player.play() : player.pause();
  }
  if (e.code === 'BracketLeft') { startTime = player.currentTime; updateHandles(); updateInputs(); }
  if (e.code === 'BracketRight') { endTime = player.currentTime; updateHandles(); updateInputs(); }
});
</script>
</body>
</html>
'''

with open(templates_dir / 'index.html', 'w') as f:
    f.write(HTML_TEMPLATE)

if __name__ == '__main__':
    print("Starting Media Cutter...")
    print("Make sure ffmpeg and yt-dlp are installed:")
    print("  sudo apt install ffmpeg  OR  brew install ffmpeg")
    print("  pip install yt-dlp flask")
    app.run(debug=True, host='0.0.0.0', port=5000)
