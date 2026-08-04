import os
import json
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
from config import Config
from utils.media_processor import MediaProcessor
from utils.youtube_handler import YouTubeHandler

app = Flask(__name__)
app.config.from_object(Config)

# Create necessary directories
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    if file and allowed_file(file.filename):
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}_{original_filename}"
        filepath = os.path.join(Config.UPLOAD_FOLDER, unique_filename)
        
        file.save(filepath)
        
        # Get media info
        media_info = MediaProcessor.get_media_info(filepath)
        
        if 'error' in media_info:
            os.remove(filepath)
            return jsonify({'success': False, 'error': media_info['error']})
        
        # Store in session
        session['current_media'] = {
            'filepath': filepath,
            'type': 'local',
            'filename': unique_filename,
            'info': media_info
        }
        
        return jsonify({
            'success': True,
            'filepath': filepath,
            'filename': unique_filename,
            'media_info': media_info
        })
    
    return jsonify({'success': False, 'error': 'File type not allowed'})

@app.route('/youtube', methods=['POST'])
def handle_youtube():
    """Handle YouTube URL"""
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'success': False, 'error': 'No URL provided'})
    
    # First, get video info
    info = YouTubeHandler.get_video_info(url)
    
    if not info['success']:
        return jsonify({'success': False, 'error': info.get('error', 'Failed to get video info')})
    
    # Download video
    result = YouTubeHandler.download_video(url)
    
    if not result['success']:
        return jsonify({'success': False, 'error': result.get('error', 'Download failed')})
    
    # Get media info
    media_info = MediaProcessor.get_media_info(result['filepath'])
    
    # Store in session
    session['current_media'] = {
        'filepath': result['filepath'],
        'type': 'youtube',
        'filename': result['filename'],
        'info': media_info
    }
    
    return jsonify({
        'success': True,
        'filepath': result['filepath'],
        'filename': result['filename'],
        'title': result['title'],
        'media_info': media_info
    })

@app.route('/cut', methods=['POST'])
def cut_media():
    """Cut and process media"""
    data = request.json
    filepath = data.get('filepath')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    output_format = data.get('format', 'mp4')
    quality = data.get('quality', 'high')
    
    if not all([filepath, start_time is not None, end_time is not None]):
        return jsonify({'success': False, 'error': 'Missing parameters'})
    
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': 'File not found'})
    
    # Process the cut
    result = MediaProcessor.cut_media(
        filepath,
        float(start_time),
        float(end_time),
        output_format,
        quality
    )
    
    if result['success']:
        return jsonify({
            'success': True,
            'filename': result['filename'],
            'output_path': result['output_path'],
            'download_url': f"/download/{result['filename']}"
        })
    
    return jsonify({'success': False, 'error': result.get('error', 'Processing failed')})

@app.route('/download/<filename>')
def download_file(filename):
    """Download processed file"""
    filepath = os.path.join(Config.OUTPUT_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    return jsonify({'success': False, 'error': 'File not found'}), 404

@app.route('/preview/<filename>')
def preview_file(filename):
    """Stream file for preview"""
    filepath = os.path.join(Config.OUTPUT_FOLDER, filename)
    if not os.path.exists(filepath):
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    
    if os.path.exists(filepath):
        return send_file(filepath)
    return jsonify({'success': False, 'error': 'File not found'}), 404

@app.route('/export', methods=['POST'])
def export_media():
    """Export metadata in various formats"""
    data = request.json
    export_format = data.get('format', 'json')
    media_data = data.get('media_data', {})
    
    if export_format == 'json':
        return jsonify({
            'success': True,
            'data': media_data,
            'export_time': datetime.now().isoformat()
        })
    elif export_format == 'csv':
        # Generate CSV
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=media_data.keys())
        writer.writeheader()
        writer.writerow(media_data)
        
        return jsonify({
            'success': True,
            'csv_data': output.getvalue()
        })
    
    return jsonify({'success': False, 'error': 'Unsupported format'})

@app.route('/api/info/<filename>')
def get_media_info(filename):
    """Get media information via API"""
    filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        filepath = os.path.join(Config.OUTPUT_FOLDER, filename)
    
    if os.path.exists(filepath):
        info = MediaProcessor.get_media_info(filepath)
        return jsonify(info)
    
    return jsonify({'error': 'File not found'}), 404

# Cleanup old files (run periodically)
@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Clean up old files"""
    # Implementation would depend on your storage strategy
    # This is a placeholder for custom cleanup logic
    return jsonify({'success': True, 'message': 'Cleanup completed'})

if __name__ == '__main__':
    app.secret_key = Config.SECRET_KEY
    app.run(debug=True, host='0.0.0.0', port=5000)
