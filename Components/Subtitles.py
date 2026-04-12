import os
import shutil

_magick = shutil.which("magick") or shutil.which("convert") or "/usr/bin/convert"
os.environ["IMAGEMAGICK_BINARY"] = _magick

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from moviepy.config import change_settings
change_settings({"IMAGEMAGICK_BINARY": _magick})

FONT_PATH = os.environ.get(
    "FONT_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Montserrat-ExtraBold.ttf")
)
MAX_GROUP = 3       # maximum words per group
PAUSE_THRESHOLD = 0.4  # seconds — start a new group if gap exceeds this


def _load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def _build_groups(words):
    """
    Group words by speech pauses.
    words: [{start, end, text, ...}, ...]
    Returns: [{group_words, group_start, group_end, active_indices}, ...]
    """
    if not words:
        return []

    groups = []
    current_group = [words[0]]

    for w in words[1:]:
        gap = w["start"] - current_group[-1]["end"]
        prev_text = current_group[-1]["text"].rstrip()
        ends_sentence = prev_text and prev_text[-1] in ".!?…"
        if ends_sentence or gap > PAUSE_THRESHOLD or len(current_group) >= MAX_GROUP:
            groups.append(current_group)
            current_group = [w]
        else:
            current_group.append(w)

    if current_group:
        groups.append(current_group)

    return groups


def _render_frame(group_words, active_idx, font, video_w, video_h):
    img = Image.new("RGBA", (video_w, video_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_w = int(video_w * 0.92)

    # Uppercase all words
    words_upper = [w.upper() for w in group_words]

    # Shrink font until all words fit on one line
    current_font = font
    while True:
        space_w = draw.textbbox((0, 0), " ", font=current_font)[2]
        word_widths = [draw.textbbox((0, 0), wu, font=current_font)[2] for wu in words_upper]
        total_w = sum(word_widths) + space_w * (len(words_upper) - 1)
        if total_w <= max_w or current_font.size <= 20:
            break
        current_font = _load_font(current_font.size - 4)

    space_w = draw.textbbox((0, 0), " ", font=current_font)[2]
    word_widths = [draw.textbbox((0, 0), wu, font=current_font)[2] for wu in words_upper]
    total_w = sum(word_widths) + space_w * (len(words_upper) - 1)
    sample_h = draw.textbbox((0, 0), "A", font=current_font)[3]

    x = (video_w - total_w) // 2
    y = video_h - sample_h - 130

    for i, (wu, ww) in enumerate(zip(words_upper, word_widths)):
        color = (255, 220, 0, 255) if i == active_idx else (255, 255, 255, 255)
        for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, -2), (-2, 2), (2, 2)]:
            draw.text((x + dx, y + dy), wu, font=current_font, fill=(0, 0, 0, 255))
        draw.text((x, y), wu, font=current_font, fill=color)
        x += ww + space_w

    return np.array(img)


def add_subtitles(video_path, segments, start_offset, output_path):
    print("📝 Adding subtitles...")

    video = VideoFileClip(video_path)
    video_w, video_h = video.w, video.h
    video_duration = video.duration

    font_size = max(120, video_h // 10)
    font = _load_font(font_size)

    # Filter and sort words
    words = []
    for seg in segments:
        s = seg["start"] - start_offset
        e = seg["end"] - start_offset
        if e <= 0 or s >= video_duration:
            continue
        s = max(0.0, s)
        e = min(video_duration, e)
        if e > s:
            words.append({**seg, "start": s, "end": e})

    if not words:
        video.write_videofile(output_path, codec="libx264", audio_codec="aac")
        video.close()
        return

    words.sort(key=lambda x: x["start"])

    # Group by speech pauses
    groups = _build_groups(words)

    text_clips = []

    for group in groups:
        group_texts = [w["text"] for w in group]

        for i, word in enumerate(group):
            frame = _render_frame(group_texts, i, font, video_w, video_h)
            clip = (ImageClip(frame, ismask=False)
                    .set_start(word["start"])
                    .set_duration(word["end"] - word["start"]))
            text_clips.append(clip)

    final_video = CompositeVideoClip([video] + text_clips)
    final_video.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=video.fps,
        preset="medium",
        bitrate="3000k"
    )
    video.close()
    final_video.close()
