import os
import json
import assemblyai as aai
from openai import OpenAI
from Components.Edit import extract_audio
from dotenv import load_dotenv

load_dotenv()
aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORD_CACHE = os.path.join(_DIR, "word_cache.json")
TRANSCRIPT_CACHE = os.path.join(_DIR, "transcript_cache.json")

PAUSE_THRESHOLD = 0.5  # saniye — cümle grubu sınırı


def _words_to_segments(word_segments):
    """
    AssemblyAI kelime listesinden cümle bazlı segment listesi üret.
    Noktalama işareti veya uzun duraksamada yeni cümle başlar.
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
    """GPT ile transkript metinlerindeki hataları düzelt."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Sadece metinleri gönder, timestamp'leri koru
    texts = [s["text"] for s in segments]
    combined = "\n".join(f"{i}: {t}" for i, t in enumerate(texts))

    print("✏️  GPT transkript hatalarını düzeltiyor...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": f"""Aşağıdaki Türkçe konuşma transkripti var. Her satır bir segment.
Sadece kelime/harf hatalarını düzelt. Cümle yapısını, anlamı, sırayı değiştirme.
Aynı format ile geri ver (satır numarası: metin).

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

    print("✅ Transkript düzeltildi.")
    return corrected_segments


def transcribe(video_path, use_cache=True, youtube_url=None):
    """Transkripti AssemblyAI kelime verisinden türet."""
    if use_cache and os.path.exists(TRANSCRIPT_CACHE):
        print("📋 Transkript cache'den yükleniyor...")
        with open(TRANSCRIPT_CACHE) as f:
            return json.load(f)

    # Önce word_cache varsa ondan türet
    if os.path.exists(WORD_CACHE):
        print("📋 Kelime verisinden transkript türetiliyor...")
        with open(WORD_CACHE) as f:
            word_segments = json.load(f)
    else:
        word_segments = get_word_timed_segments(video_path)

    segments = _words_to_segments(word_segments)
    segments = _correct_transcript(segments)

    with open(TRANSCRIPT_CACHE, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(segments)} segment oluşturuldu.")
    return segments


def get_word_timed_segments(video_path, youtube_segments=None):
    """AssemblyAI ile kelime bazlı hassas zamanlama."""
    if os.path.exists(WORD_CACHE):
        print("📋 Kelime zamanlaması cache'den yükleniyor...")
        with open(WORD_CACHE) as f:
            return json.load(f)

    print("⏱️  Kelime zamanlaması hesaplanıyor (AssemblyAI)...")
    audio_path = extract_audio(video_path)

    transcriber = aai.Transcriber()
    config = aai.TranscriptionConfig(language_code="tr", speech_models=["universal-2"])
    result = transcriber.transcribe(audio_path, config=config)

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

    # Overlap düzelt
    for i in range(len(word_segments) - 1):
        if word_segments[i]["end"] > word_segments[i + 1]["start"]:
            word_segments[i]["end"] = word_segments[i + 1]["start"]

    with open(WORD_CACHE, "w", encoding="utf-8") as f:
        json.dump(word_segments, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(word_segments)} kelime zamanlaması hesaplandı.")
    return word_segments
