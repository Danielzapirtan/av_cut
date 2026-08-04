class MediaCutter {
    constructor() {
        this.mediaFile = null;
        this.duration = 0;
        this.startTime = 0;
        this.endTime = 0;
        this.isDragging = false;
        this.activeHandle = null;
        
        this.initializeElements();
        this.attachEventListeners();
    }
    
    initializeElements() {
        this.fileUpload = document.getElementById('fileUpload');
        this.youtubeUrl = document.getElementById('youtubeUrl');
        this.youtubeBtn = document.getElementById('youtubeBtn');
        this.mediaPlayer = document.getElementById('mediaPlayer');
        this.previewPlayer = document.getElementById('previewPlayer');
        this.startTimeInput = document.getElementById('startTime');
        this.endTimeInput = document.getElementById('endTime');
        this.startHandle = document.getElementById('startHandle');
        this.endHandle = document.getElementById('endHandle');
        this.selection = document.getElementById('selection');
        this.timeline = document.getElementById('timeline');
        this.cutBtn = document.getElementById('cutBtn');
        this.outputFormat = document.getElementById('outputFormat');
        this.quality = document.getElementById('quality');
        this.editorSection = document.getElementById('editorSection');
        this.mediaInfo = document.getElementById('mediaInfo');
        this.mediaDetails = document.getElementById('mediaDetails');
        this.previewSection = document.getElementById('previewSection');
    }
    
    attachEventListeners() {
        // File upload
        this.fileUpload.addEventListener('change', (e) => this.handleFileUpload(e));
        
        // YouTube download
        this.youtubeBtn.addEventListener('click', () => this.handleYouTubeDownload());
        
        // Timeline handles
        this.startHandle.addEventListener('mousedown', (e) => this.startDrag(e, 'start'));
        this.endHandle.addEventListener('mousedown', (e) => this.startDrag(e, 'end'));
        document.addEventListener('mousemove', (e) => this.drag(e));
        document.addEventListener('mouseup', () => this.stopDrag());
        
        // Time inputs
        this.startTimeInput.addEventListener('change', () => this.updateFromTimeInput('start'));
        this.endTimeInput.addEventListener('change', () => this.updateFromTimeInput('end'));
        
        // Media player time update
        this.mediaPlayer.addEventListener('timeupdate', () => this.updatePlayerTime());
        
        // Cut button
        this.cutBtn.addEventListener('click', () => this.cutMedia());
        
        // Export buttons
        document.getElementById('exportJsonBtn')?.addEventListener('click', () => this.exportData('json'));
        document.getElementById('exportCsvBtn')?.addEventListener('click', () => this.exportData('csv'));
        
        // Timeline click
        this.timeline.addEventListener('click', (e) => this.handleTimelineClick(e));
    }
    
    async handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.loadMedia(data);
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            console.error('Upload error:', error);
            alert('Upload failed');
        }
    }
    
    async handleYouTubeDownload() {
        const url = this.youtubeUrl.value.trim();
        if (!url) {
            alert('Please enter a YouTube URL');
            return;
        }
        
        try {
            const response = await fetch('/youtube', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: url })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.loadMedia(data);
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            console.error('YouTube download error:', error);
            alert('Download failed');
        }
    }
    
    loadMedia(data) {
        this.mediaFile = data;
        this.duration = data.media_info.duration;
        
        // Set video source
        this.mediaPlayer.src = `/preview/${data.filename}`;
        this.mediaPlayer.load();
        
        // Reset times
        this.startTime = 0;
        this.endTime = this.duration;
        this.startTimeInput.value = this.formatTime(0);
        this.endTimeInput.value = this.formatTime(this.duration);
        
        // Update UI
        this.updateTimeline();
        this.editorSection.style.display = 'block';
        this.mediaInfo.style.display = 'block';
        
        // Display media info
        this.mediaDetails.innerHTML = `
            <p>Duration: ${data.media_info.duration_formatted}</p>
            <p>Size: ${data.media_info.size_mb} MB</p>
            ${data.media_info.has_video ? `<p>Video: ${data.media_info.width}x${data.media_info.height} @ ${data.media_info.fps}fps</p>` : ''}
            <p>Audio: ${data.media_info.has_audio ? 'Yes' : 'No'}</p>
        `;
    }
    
    formatTime(seconds) {
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    
    parseTime(timeString) {
        const parts = timeString.split(':');
        return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseFloat(parts[2]);
    }
    
    updateTimeline() {
        if (this.duration === 0) return;
        
        const startPercent = (this.startTime / this.duration) * 100;
        const endPercent = (this.endTime / this.duration) * 100;
        
        this.startHandle.style.left = startPercent + '%';
        this.endHandle.style.left = endPercent + '%';
        this.selection.style.left = startPercent + '%';
        this.selection.style.width = (endPercent - startPercent) + '%';
    }
    
    updateReverseTimeline() {
        if (this.duration === 0) return;
        
	const startPercent = this.startHandle.style.left;
	const endPercent = this.endHandle.style.left;
	this.startTime = startPercent * this.duration / 100;
	this.endTime = endPercent * this.duration / 100;
    }
    
    startDrag(event, handle) {
        event.preventDefault();
        this.isDragging = true;
        this.activeHandle = handle;
    }
    
    drag(event) {
        if (!this.isDragging) return;
        
        const timelineRect = this.timeline.getBoundingClientRect();
        const x = event.clientX - timelineRect.left;
        const percent = Math.max(0, Math.min(100, (x / timelineRect.width) * 100));
        const time = (percent / 100) * this.duration;
        
        if (this.activeHandle === 'start') {
            if (time < this.endTime - 1) {
                this.startTime = time;
                this.startTimeInput.value = this.formatTime(time);
            }
        } else if (this.activeHandle === 'end') {
            if (time > this.startTime + 1) {
                this.endTime = time;
                this.endTimeInput.value = this.formatTime(time);
            }
        }
        
        this.updateReverseTimeline();
    }
    
    stopDrag() {
        this.isDragging = false;
        this.activeHandle = null;
    }
    
    updateFromTimeInput(which) {
        const time = this.parseTime(which === 'start' ? this.startTimeInput.value : this.endTimeInput.value);
        
        if (which === 'start' && time < this.endTime) {
            this.startTime = time;
        } else if (which === 'end' && time > this.startTime) {
            this.endTime = Math.min(time, this.duration);
        }
        
        this.updateTimeline();
    }
    
    updatePlayerTime() {
        // You could add auto-scrolling or other features here
    }
    
    handleTimelineClick(event) {
        const timelineRect = this.timeline.getBoundingClientRect();
        const x = event.clientX - timelineRect.left;
        const percent = (x / timelineRect.width) * 100;
        const time = (percent / 100) * this.duration;
        
        this.mediaPlayer.currentTime = time;
    }
    
    async cutMedia() {
        if (!this.mediaFile) {
            alert('Please load a media file first');
            return;
        }
        
        const data = {
            filepath: this.mediaFile.filepath,
            start_time: this.startTime,
            end_time: this.endTime,
            format: this.outputFormat.value,
            quality: this.quality.value
        };
        
        try {
            const response = await fetch('/cut', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Show preview
                this.previewPlayer.src = result.download_url;
                this.previewSection.style.display = 'block';
                
                // Trigger download
                window.location.href = result.download_url;
            } else {
                alert('Error: ' + result.error);
            }
        } catch (error) {
            console.error('Cut error:', error);
            alert('Processing failed');
        }
    }
    
    async exportData(format) {
        const mediaData = {
            title: this.mediaFile?.title || 'Untitled',
            filename: this.mediaFile?.filename || 'unknown',
            start: this.formatTime(this.startTime),
            end: this.formatTime(this.endTime),
            duration: this.formatTime(this.endTime - this.startTime),
            format: this.outputFormat.value,
            quality: this.quality.value,
            export_date: new Date().toISOString()
        };
        
        try {
            const response = await fetch('/export', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    format: format,
                    media_data: mediaData
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                if (format === 'json') {
                    // Download JSON
                    const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
                    this.downloadBlob(blob, 'media_export.json');
                } else if (format === 'csv') {
                    // Download CSV
                    const blob = new Blob([result.csv_data], { type: 'text/csv' });
                    this.downloadBlob(blob, 'media_export.csv');
                }
            }
        } catch (error) {
            console.error('Export error:', error);
            alert('Export failed');
        }
    }
    
    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new MediaCutter();
});
