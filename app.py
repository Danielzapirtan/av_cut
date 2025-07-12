#!/usr/bin/env python3
"""
Audio/Video Cut Application
A simple command-line tool to cut audio and video files using FFmpeg.
"""

import os
import sys
import subprocess
from pathlib import Path
import re

def check_ffmpeg():
    """Check if FFmpeg is installed and available."""
    try:
        subprocess.run(['ffmpeg', '-version'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, 
                      check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def parse_time(time_str):
    """
    Parse time string in formats like:
    - 10 (seconds)
    - 1:30 (minutes:seconds)
    - 1:30:45 (hours:minutes:seconds)
    - 90.5 (seconds with decimal)
    """
    time_str = time_str.strip()
    
    # Handle decimal seconds
    if re.match(r'^\d+(\.\d+)?$', time_str):
        return float(time_str)
    
    # Handle time format (HH:MM:SS or MM:SS)
    parts = time_str.split(':')
    if len(parts) == 2:  # MM:SS
        minutes, seconds = map(float, parts)
        return minutes * 60 + seconds
    elif len(parts) == 3:  # HH:MM:SS
        hours, minutes, seconds = map(float, parts)
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError(f"Invalid time format: {time_str}")

def format_time(seconds):
    """Format seconds as HH:MM:SS.sss"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

def get_media_duration(file_path):
    """Get the duration of a media file using ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None

def cut_media(input_path, output_path, start_time, end_time):
    """Cut media file using FFmpeg."""
    try:
        duration = end_time - start_time
        
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-ss', format_time(start_time),
            '-t', format_time(duration),
            '-c', 'copy',  # Copy streams without re-encoding for speed
            '-avoid_negative_ts', 'make_zero',
            str(output_path),
            '-y'  # Overwrite output file if it exists
        ]
        
        print(f"Cutting media from {format_time(start_time)} to {format_time(end_time)}...")
        print(f"Duration: {format_time(duration)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return True, "Success"
        else:
            return False, result.stderr
            
    except Exception as e:
        return False, str(e)

def get_output_filename(input_path, start_time, end_time):
    """Generate output filename based on input file and time range."""
    input_path = Path(input_path)
    stem = input_path.stem
    suffix = input_path.suffix
    
    start_str = format_time(start_time).replace(':', '-')
    end_str = format_time(end_time).replace(':', '-')
    
    return f"{stem}_cut_{start_str}_to_{end_str}{suffix}"

def main():
    print("Audio/Video Cut Application")
    print("=" * 30)
    
    # Check if FFmpeg is installed
    if not check_ffmpeg():
        print("Error: FFmpeg is not installed or not found in PATH.")
        print("Please install FFmpeg and make sure it's accessible from the command line.")
        print("Visit https://ffmpeg.org/download.html for installation instructions.")
        return 1
    
    # Get input file path
    while True:
        input_path = input("Enter the path to the video/audio file: ").strip()
        if not input_path:
            print("Please enter a valid file path.")
            continue
            
        input_path = Path(input_path)
        if not input_path.exists():
            print(f"Error: File '{input_path}' does not exist.")
            continue
            
        if not input_path.is_file():
            print(f"Error: '{input_path}' is not a file.")
            continue
            
        break
    
    # Get media duration
    print("\nAnalyzing media file...")
    total_duration = get_media_duration(input_path)
    if total_duration:
        print(f"Media duration: {format_time(total_duration)}")
    else:
        print("Warning: Could not determine media duration.")
    
    # Get start time
    while True:
        try:
            start_input = input("\nEnter start time (e.g., 10, 1:30, 1:30:45): ").strip()
            if not start_input:
                print("Please enter a start time.")
                continue
                
            start_time = parse_time(start_input)
            if start_time < 0:
                print("Start time cannot be negative.")
                continue
                
            if total_duration and start_time >= total_duration:
                print(f"Start time cannot be greater than or equal to media duration ({format_time(total_duration)}).")
                continue
                
            break
        except ValueError as e:
            print(f"Error: {e}")
            print("Please use format: seconds (10), minutes:seconds (1:30), or hours:minutes:seconds (1:30:45)")
    
    # Get end time
    while True:
        try:
            end_input = input("Enter end time (e.g., 60, 2:30, 2:30:45): ").strip()
            if not end_input:
                print("Please enter an end time.")
                continue
                
            end_time = parse_time(end_input)
            if end_time <= start_time:
                print("End time must be greater than start time.")
                continue
                
            if total_duration and end_time > total_duration:
                print(f"End time cannot be greater than media duration ({format_time(total_duration)}).")
                continue
                
            break
        except ValueError as e:
            print(f"Error: {e}")
            print("Please use format: seconds (60), minutes:seconds (2:30), or hours:minutes:seconds (2:30:45)")
    
    # Generate output filename
    output_filename = get_output_filename(input_path, start_time, end_time)
    output_path = Path.cwd() / output_filename
    
    print(f"\nOutput file: {output_path}")
    
    # Confirm before processing
    confirm = input("\nProceed with cutting? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("Operation cancelled.")
        return 0
    
    # Cut the media
    success, message = cut_media(input_path, output_path, start_time, end_time)
    
    if success:
        print(f"\n✓ Successfully created: {output_path}")
        print(f"File size: {output_path.stat().st_size / (1024*1024):.2f} MB")
    else:
        print(f"\n✗ Error cutting media: {message}")
        return 1
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
