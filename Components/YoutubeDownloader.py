import subprocess
import json
import os
import sys
import shutil

_YTDLP = shutil.which("yt-dlp") or "yt-dlp"


def download_video(url, output_dir=None):
    """Download YouTube video using yt-dlp, best quality mp4."""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "youtubevideos")
    os.makedirs(output_dir, exist_ok=True)
    print(f"📥 YouTube videosu indiriliyor: {url}")

    # Get video info
    result = subprocess.run(
        [_YTDLP, "-J", "--no-playlist", url],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"❌ Failed to fetch video info:\n{result.stderr}")
        sys.exit(1)

    info = json.loads(result.stdout)
    title = info.get("title", "video")
    duration = info.get("duration", 0)

    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
    safe_title = safe_title[:80]
    output_path = os.path.join(output_dir, f"{safe_title}.mp4")

    print(f"🎬 Video: {title}")
    print(f"⏱  Duration: {duration}s ({duration // 60}m {duration % 60}s)")

    cmd = [
        _YTDLP,
        "-f", "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--extractor-args", "youtube:player_client=tv,-android_vr",
        "-o", output_path,
        "--no-playlist",
        url
    ]
    # Mac'te Chrome cookie'si kullan (container'da yok)
    if shutil.which("google-chrome") or shutil.which("chromium") or os.path.exists("/Applications/Google Chrome.app"):
        cmd += ["--cookies-from-browser", "chrome"]

    subprocess.run(cmd, check=True)

    print(f"✅ Downloaded: {output_path}")
    return output_path
