import os
import json
import assemblyai as aai
from openai import OpenAI
from Components.Edit import extract_audio
from dotenv import load_dotenv

load_dotenv()
aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cache_paths(video_path):
    base = os.path.splitext(os.path.basename(video_path))[0]
    return (
        os.path.join(_DIR, f"transcript_cache_{base}.json"),
        os.path.join(_DIR, f"word_cache_{base}.json")
    )

PAUSE_THRESHOLD = 0.5  # seconds — sentence group boundary


def _words_to_segments(word_segments):
    """
    Build sentence-level segments from AssemblyAI word list.
    A new sentence starts on punctuation or a long pause.
    """
    if not word_segments:
        return []

    segments = []
    current_words = [word_segments[0]]

    for w in word_segments[1:]:
        prev = current_words[-1]
        gap = w["start"] - prev["end"]
        ends_sentence = prev["text"].rstrip().rstrip("\"'»").endswith((".", "!", "?", "…"))

        if ends_sentence or gap > PAUSE_THRESHOLD:
            text = " ".join(cw["text"] for cw in current_words)
            segments.append({
                "start": current_words[0]["start"],
                "end": prev["end"],
                "text": text
            })
            current_words = [w]
        else:
            current_words.append(w)

    if current_words:
        text = " ".join(cw["text"] for cw in current_words)
        segments.append({
            "start": current_words[0]["start"],
            "end": current_words[-1]["end"],
            "text": text
        })

    return segments


def _correct_transcript(segments):
    """Use GPT to fix transcription errors in the text."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    texts = [s["text"] for s in segments]
    combined = "\n".join(f"{i}: {t}" for i, t in enumerate(texts))

    print("✏️  GPT correcting transcript errors...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": f"""Below is a speech transcript. Each line is a segment.
Fix only word/spelling errors. Do not change sentence structure, meaning, or order.
Return in the same format (line number: text).

{combined}"""
        }],
        temperature=0.0
    )

    corrected_lines = response.choices[0].message.content.strip().split("\n")
    corrected_texts = {}
    for line in corrected_lines:
        if ": " in line:
            idx, text = line.split(": ", 1)
            try:
                corrected_texts[int(idx.strip())] = text.strip()
            except ValueError:
                pass

    corrected_segments = []
    for i, seg in enumerate(segments):
        corrected_segments.append({
            **seg,
            "text": corrected_texts.get(i, seg["text"])
        })

    print("✅ Transcript corrected.")
    return corrected_segments


def transcribe(video_path, use_cache=True, youtube_url=None):
    """Build transcript from AssemblyAI word data."""
    TRANSCRIPT_CACHE, WORD_CACHE = _cache_paths(video_path)

    if use_cache and os.path.exists(TRANSCRIPT_CACHE):
        print("📋 Loading transcript from cache...")
        with open(TRANSCRIPT_CACHE) as f:
            return json.load(f)

    if os.path.exists(WORD_CACHE):
        print("📋 Building transcript from word cache...")
        with open(WORD_CACHE) as f:
            word_segments = json.load(f)
    else:
        word_segments = get_word_timed_segments(video_path)

    segments = _words_to_segments(word_segments)
    segments = _correct_transcript(segments)

    with open(TRANSCRIPT_CACHE, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(segments)} segments created.")
    return segments


def get_word_timed_segments(video_path, youtube_segments=None):
    """Get word-level timing from AssemblyAI."""
    _, WORD_CACHE = _cache_paths(video_path)

    if os.path.exists(WORD_CACHE):
        print("📋 Loading word timing from cache...")
        with open(WORD_CACHE) as f:
            return json.load(f)

    print("⏱️  Computing word timing (AssemblyAI)...")
    audio_path = extract_audio(video_path)

    transcriber = aai.Transcriber()
    config = aai.TranscriptionConfig(language_detection=True, speech_models=["universal-2"])
    result = transcriber.transcribe(audio_path, config=config)
    print(f"🌐 Detected language: {result.json_response.get('language_code', '?')}")

    if os.path.exists(audio_path):
        os.remove(audio_path)

    OFFSET = 0.05
    word_segments = []
    for word in (result.words or []):
        w_start = round(word.start / 1000.0 + OFFSET, 3)
        w_end = round(word.end / 1000.0 + OFFSET, 3)
        word_segments.append({
            "start": w_start,
            "end": w_end,
            "text": word.text
        })

    # Fix overlaps
    for i in range(len(word_segments) - 1):
        if word_segments[i]["end"] > word_segments[i + 1]["start"]:
            word_segments[i]["end"] = word_segments[i + 1]["start"]

    _, WORD_CACHE = _cache_paths(video_path)
    with open(WORD_CACHE, "w", encoding="utf-8") as f:
        json.dump(word_segments, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(word_segments)} word timings computed.")
    return word_segments
