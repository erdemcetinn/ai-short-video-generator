import subprocess
import json
import os
import sys


def download_video(url, output_dir="."):
    """Download YouTube video using yt-dlp, best quality mp4."""
    print(f"📥 YouTube videosu indiriliyor: {url}")

    # Get video info
    result = subprocess.run(
        ["yt-dlp", "-J", "--no-playlist", url],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"❌ Video bilgisi alınamadı:\n{result.stderr}")
        sys.exit(1)

    info = json.loads(result.stdout)
    title = info.get("title", "video")
    duration = info.get("duration", 0)

    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
    safe_title = safe_title[:80]
    output_path = os.path.join(output_dir, f"{safe_title}.mp4")

    print(f"🎬 Video: {title}")
    print(f"⏱  Süre: {duration}s ({duration // 60}dk {duration % 60}sn)")

    subprocess.run([
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_path,
        "--no-playlist",
        url
    ], check=True)

    print(f"✅ İndirildi: {output_path}")
    return output_path
