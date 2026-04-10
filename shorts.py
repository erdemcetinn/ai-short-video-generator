import os
import sys
import json
import subprocess
import whisper
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# =====================
# AYARLAR
# =====================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INPUT_VIDEO = "20li_yaslar.mp4"
OUTPUT_FOLDER = "shorts"
SHORT_DURATION = 60
NUM_SHORTS = 3
TRANSCRIPT_CACHE = "transcript_cache.json"
# =====================

client = OpenAI(api_key=OPENAI_API_KEY)

def get_video_duration(video_path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])

def transcribe_video(video_path):
    if os.path.exists(TRANSCRIPT_CACHE):
        print("📋 Transkript cache'den yükleniyor...")
        with open(TRANSCRIPT_CACHE) as f:
            return json.load(f)

    print("🎤 Ses metne çevriliyor (Whisper)...")
    audio_path = "temp_audio.mp3"
    subprocess.run([
        "ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a",
        audio_path, "-y", "-loglevel", "quiet"
    ])
    m = whisper.load_model("base")
    r = m.transcribe(audio_path, verbose=False)
    os.remove(audio_path)

    with open(TRANSCRIPT_CACHE, "w") as f:
        json.dump(r["segments"], f)

    return r["segments"]

def find_best_segments(segments, duration, num_shorts, short_duration):
    print("🤖 GPT en iyi bölümleri seçiyor...")

    segments_text = ""
    for seg in segments:
        segments_text += f"[{seg['start']:.0f}s - {seg['end']:.0f}s]: {seg['text']}\n"

    prompt = f"""Aşağıda bir videonun transkripti var.
Video süresi: {duration:.0f} saniye.
Her short için süre: {short_duration} saniye.

En ilgi çekici, viral olabilecek {num_shorts} bölümü seç.
Her bölüm için start_time ve end_time ver (fark tam {short_duration} saniye olsun).

Transkript:
{segments_text}

Sadece JSON formatında cevap ver, başka hiçbir şey yazma:
{{
  "segments": [
    {{"start_time": 10, "end_time": 70, "reason": "neden seçildi"}},
    ...
  ]
}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    text = response.choices[0].message.content
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)["segments"]

def crop_to_vertical(input_path, output_path, start, end):
    print(f"✂️  Kırpılıyor: {start}s - {end}s")
    subprocess.run([
        "ffmpeg", "-i", input_path,
        "-ss", str(start), "-to", str(end),
        "-vf", "crop=ih*9/16:ih,scale=1080:1920",
        "-c:v", "libx264", "-c:a", "aac",
        "-y", output_path, "-loglevel", "quiet"
    ])

def main():
    if not os.path.exists(INPUT_VIDEO):
        print(f"❌ Video bulunamadı: {INPUT_VIDEO}")
        sys.exit(1)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    print(f"📹 Video: {INPUT_VIDEO}")
    duration = get_video_duration(INPUT_VIDEO)
    print(f"⏱  Süre: {duration:.0f} saniye")

    segments = transcribe_video(INPUT_VIDEO)
    best = find_best_segments(segments, duration, NUM_SHORTS, SHORT_DURATION)

    print(f"\n✅ {len(best)} bölüm seçildi:\n")
    for i, seg in enumerate(best):
        print(f"  Short {i+1}: {seg['start_time']}s - {seg['end_time']}s")
        print(f"  Neden: {seg['reason']}\n")

        output_path = os.path.join(OUTPUT_FOLDER, f"short_{i+1}.mp4")
        crop_to_vertical(INPUT_VIDEO, output_path, seg["start_time"], seg["end_time"])
        print(f"  💾 Kaydedildi: {output_path}\n")

    print("🎉 Tamamlandı! shorts klasörüne bak.")

if __name__ == "__main__":
    main()