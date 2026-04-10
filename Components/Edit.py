import subprocess
import json
import os


def get_video_duration(video_path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def extract_audio(video_path, audio_path="temp_audio.wav"):
    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        audio_path, "-y", "-loglevel", "quiet"
    ], check=True)
    return audio_path
