import os
import sys
import json
import subprocess
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import uuid
import argparse
import threading
from dotenv import load_dotenv

load_dotenv()

def download_from_s3(s3_url, local_path):
    """s3://bucket/key/video.mp4 → local_path"""
    import boto3
    s3_url = s3_url.replace("s3://", "")
    bucket, key = s3_url.split("/", 1)
    print(f"⬇️  Downloading from S3: s3://{bucket}/{key}")
    boto3.client("s3").download_file(bucket, key, local_path)
    print(f"✅ Downloaded: {local_path}")
    return local_path


def upload_to_s3(local_path, bucket, key):
    """local_path → s3://bucket/key"""
    import boto3
    print(f"⬆️  Uploading to S3: s3://{bucket}/{key}")
    boto3.client("s3").upload_file(local_path, bucket, key)
    print(f"✅ Uploaded: s3://{bucket}/{key}")

from Components.Edit import get_video_duration
from Components.Transcription import transcribe, get_word_timed_segments
from Components.LanguageTasks import find_best_segment
from Components.FaceCrop import crop_to_vertical
from Components.Subtitles import add_subtitles
from Components.YoutubeDownloader import download_video

OUTPUT_FOLDER = "shorts"
DEFAULT_SHORT_DURATION = 60
DEFAULT_NUM_SHORTS = 1


def pick_segment(candidates):
    """
    Show 3 candidates to the user and let them pick by number.
    Returns the selected segment dict, or None to cancel.
    """
    print(f"\n{'=' * 60}")
    print(f"🎯  GPT's 3 Suggestions:")
    print(f"{'=' * 60}")

    for i, seg in enumerate(candidates, 1):
        duration = seg["end_time"] - seg["start_time"]
        print(f"\n  [{i}]  {seg['start_time']:.0f}s – {seg['end_time']:.0f}s  ({duration:.0f}s)  "
              f"🔥 Viral: {seg['viral_score']:.0f}/100")
        print(f"       Why: {seg['reason']}")
        print(f"       Transcript: {seg.get('transcript', '')}")

    print(f"\n{'=' * 60}")
    print("  Pick (1/2/3) or [Y] regenerate, [C] cancel:")

    while True:
        try:
            choice = input("  > ").strip().lower()
            if choice in ("1", "2", "3"):
                return candidates[int(choice) - 1]
            elif choice in ("y", "regenerate"):
                return "regenerate"
            elif choice in ("c", "cancel"):
                return None
            else:
                print("  ⚠️  Enter 1, 2, 3, Y or C.")
        except (KeyboardInterrupt, EOFError):
            return None


def process_short(video_path, seg, all_segments, word_segments, index, session_id, short_duration, user_prompt=None):
    """Crop, add subtitles, and save a single short."""
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    start = seg["start_time"]
    transcript_text = seg.get("transcript", "")
    last_word_text = transcript_text.strip().split()[-1].lower().strip(".,!?\"'") if transcript_text else ""
    end = seg["end_time"]
    if last_word_text:
        matches = [w for w in word_segments if w["text"].lower().strip(".,!?\"'") == last_word_text
                   and w["start"] >= seg["start_time"] and w["start"] <= seg["end_time"] + 5]
        if matches:
            end = max(matches, key=lambda w: w["start"])["end"]

    # Step 1: Face-aware vertical crop
    cropped_path = f"temp_cropped_{session_id}_{index}.mp4"
    crop_to_vertical(video_path, cropped_path, start, end)

    # Step 2: Filter word segments for this time window
    sub_segments = [
        s for s in word_segments
        if s["end"] > start and s["start"] < end
    ]

    # Step 3: Add synchronized subtitles
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_path = os.path.join(OUTPUT_FOLDER, f"{video_name}_short.mp4")
    add_subtitles(cropped_path, sub_segments, start, output_path)

    # Cleanup temp file
    if os.path.exists(cropped_path):
        os.remove(cropped_path)

    print(f"  💾 Saved: {output_path}\n")
    return output_path


LAST_VIDEO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_video.json")


def _ask_with_dialog():
    """Run dialog_helper.py as a separate process to avoid freezing."""
    helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dialog_helper.py")
    try:
        result = subprocess.run(
            [sys.executable, helper],
            capture_output=True, text=True, timeout=180
        )
        text = result.stdout.strip()
        return text if text else None
    except Exception:
        print("\n🎯 Which part of the video should we turn into a short? (leave blank = AI decides)")
        text = input("  > ").strip()
        return text if text else None


def _load_last_video():
    if os.path.exists(LAST_VIDEO_FILE):
        try:
            with open(LAST_VIDEO_FILE) as f:
                data = json.load(f)
                return data.get("path"), data.get("youtube_url")
        except Exception:
            pass
    return None, None


def _save_last_video(path, youtube_url=None):
    with open(LAST_VIDEO_FILE, "w") as f:
        json.dump({"path": path, "youtube_url": youtube_url}, f)


def _pick_file_dialog():
    """Open macOS native file picker."""
    script = '''
    set f to choose file with prompt "Select a video file:" of type {"public.movie", "public.video"}
    return POSIX path of f
    '''
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
        path = result.stdout.strip()
        return path if path and os.path.exists(path) else None
    except Exception:
        return None


def _ask_source_dialog():
    """Ask: YouTube or local file."""
    script = '''
    set choice to button returned of (display dialog "Select video source:" ¬
        buttons {"Download from YouTube", "Local File"} ¬
        default button "Local File" ¬
        with title "AI Shorts Generator")
    return choice
    '''
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)
        return result.stdout.strip()
    except Exception:
        return "Local File"


def ask_setup():
    """Interactively ask the user for input video."""
    print("\n" + "=" * 55)
    print("  🎬  AI YouTube Shorts Generator")
    print("=" * 55)

    num_shorts = DEFAULT_NUM_SHORTS
    last_path, last_yt = _load_last_video()
    youtube_url = None

    if last_path and os.path.exists(last_path):
        print(f"\n📁 Last video: {last_path}")
        choice = input("  [1] Use same video  [2] Pick new video: ").strip()
        if choice == "1":
            video_input = last_path
            youtube_url = last_yt
        else:
            video_input = None
    else:
        video_input = None

    if video_input is None:
        source = _ask_source_dialog()
        if source == "Download from YouTube":
            url = input("\n🔗 YouTube URL: ").strip()
            youtube_url = url
            video_input = download_video(url)
        else:
            picked = _pick_file_dialog()
            if picked:
                video_input = picked
                print(f"  📁 Selected: {picked}")
            else:
                while True:
                    path = input("\n📁 Enter video path: ").strip().strip('"')
                    if os.path.exists(path):
                        video_input = path
                        break
                    print(f"  ❌ Not found: {path}")

    user_prompt = _ask_with_dialog()
    if user_prompt:
        print(f"  📝 Prompt: {user_prompt}")
    else:
        print("  🤖 No prompt given — AI will select the best segment.")

    return video_input, youtube_url, user_prompt or None, num_shorts


def main():
    parser = argparse.ArgumentParser(
        description="AI YouTube Shorts Generator — Extract viral short clips from long videos"
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve GPT's top segment selection (batch mode)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=DEFAULT_SHORT_DURATION,
        help=f"Target duration of each short in seconds (default: {DEFAULT_SHORT_DURATION})"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore transcript cache and re-transcribe"
    )
    parser.add_argument(
        "--video",
        type=str,
        default=None,
        help="Path or S3 URL of the video (skips interactive setup)"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Segment description (blank = AI selects)"
    )
    parser.add_argument(
        "--s3-output",
        type=str,
        default=None,
        help="S3 folder to upload the output short to (e.g. s3://bucket/output/)"
    )
    args = parser.parse_args()

    if args.video:
        if args.video.startswith("s3://"):
            filename = args.video.split("/")[-1]
            video_input = download_from_s3(args.video, f"/tmp/{filename}")
        else:
            video_input = args.video
        youtube_url = None
        user_prompt = args.prompt
        num_shorts = DEFAULT_NUM_SHORTS
    else:
        video_input, youtube_url, user_prompt, num_shorts = ask_setup()

    session_id = str(uuid.uuid4())[:8]

    video_path = video_input
    _save_last_video(video_path, youtube_url)

    print(f"\n📹 Video: {video_path}")
    duration = get_video_duration(video_path)
    print(f"⏱  Duration: {duration:.0f}s ({duration / 60:.1f} min)")

    use_cache = not args.no_cache
    segments = transcribe(video_path, use_cache=use_cache, youtube_url=youtube_url)
    print(f"📝 {len(segments)} transcript segments")

    word_segments = get_word_timed_segments(video_path, segments)

    produced = 0
    attempts = 0
    max_attempts = num_shorts * 4
    excluded_ranges = []

    print(f"\n🎯 Target: {num_shorts} short × {args.duration}s\n")

    while produced < num_shorts and attempts < max_attempts:
        attempts += 1

        print(f"🤖 GPT selecting 3 segments...")
        candidates = find_best_segment(
            segments,
            duration,
            short_duration=args.duration,
            excluded_ranges=excluded_ranges if excluded_ranges else None,
            user_prompt=user_prompt
        )

        if args.auto_approve:
            seg = candidates[0]
            print(f"  ✅ Auto-approved: {seg['start_time']:.0f}s – {seg['end_time']:.0f}s")
        else:
            seg = pick_segment(candidates)

        if seg == "regenerate":
            print("  🔄 Regenerating...\n")
            continue
        elif seg is None:
            print("  ❌ Cancelled.")
            break

        print(f"\n⚙️  Processing short...")
        output_path = process_short(video_path, seg, segments, word_segments, produced + 1, session_id, args.duration, user_prompt)

        if args.s3_output and output_path and os.path.exists(output_path):
            s3_url = args.s3_output.rstrip("/")
            s3_url = s3_url.replace("s3://", "")
            bucket, prefix = s3_url.split("/", 1)
            key = f"{prefix}/{os.path.basename(output_path)}"
            upload_to_s3(output_path, bucket, key)

        excluded_ranges.append((seg["start_time"], seg["end_time"]))
        produced += 1

    print(f"\n🎉 Done! {produced} short(s) saved to '{OUTPUT_FOLDER}/'.")
    if produced > 0:
        print(f"   Session ID: {session_id}")


if __name__ == "__main__":
    main()
