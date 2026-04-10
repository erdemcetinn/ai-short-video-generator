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
    print(f"🎯  GPT'nin 3 Önerisi:")
    print(f"{'=' * 60}")

    for i, seg in enumerate(candidates, 1):
        duration = seg["end_time"] - seg["start_time"]
        print(f"\n  [{i}]  {seg['start_time']:.0f}s – {seg['end_time']:.0f}s  ({duration:.0f} sn)  "
              f"🔥 Viral: {seg['viral_score']:.0f}/100")
        print(f"       Neden : {seg['reason']}")
        print(f"       Transkript: {seg.get('transcript', '')}")

    print(f"\n{'=' * 60}")
    print("  Seçim yap (1/2/3) veya [Y] yeniden üret, [İ] iptal:")

    while True:
        try:
            choice = input("  > ").strip().lower()
            if choice in ("1", "2", "3"):
                return candidates[int(choice) - 1]
            elif choice in ("y", "yeniden"):
                return "regenerate"
            elif choice in ("i", "iptal"):
                return None
            else:
                print("  ⚠️  1, 2, 3, Y veya İ gir.")
        except (KeyboardInterrupt, EOFError):
            return None




def _snap_to_sentence_start(seg_start, word_segments, lookahead=6.0):
    """
    AssemblyAI kelime verisini kullanarak start_time'dan itibaren
    ilk gerçek cümle başlangıcını bul.
    Önceki kelime .!? ile bitiyorsa bir sonraki kelime cümle başıdır.
    """
    sorted_words = sorted(word_segments, key=lambda w: w["start"])
    window = [w for w in sorted_words if w["start"] >= seg_start - 0.5 and w["start"] <= seg_start + lookahead]

    for i, w in enumerate(window):
        if i == 0:
            # İlk kelimeden önceki kelimeyi bul
            prev_words = [p for p in sorted_words if p["end"] <= w["start"] + 0.1 and p["start"] < w["start"]]
            if not prev_words:
                return w["start"]  # videonun başı
            prev = max(prev_words, key=lambda p: p["end"])
        else:
            prev = window[i - 1]

        if prev["text"].rstrip().rstrip("\"'»").endswith((".", "!", "?", "…")):
            return w["start"]

    return seg_start


def _find_phrase_in_words(seg_start, word_segments, user_prompt, window=30.0):
    """
    user_prompt varsa: prompttaki anlamlı kelimeleri AssemblyAI word_segments'te ara,
    GPT'nin bölgesi etrafında bul, tam o kelimenin timestamp'ini döndür.
    user_prompt yoksa: seg_start'ı döndür.
    """
    if not user_prompt:
        return seg_start

    stopwords = {"ve", "ile", "bir", "bu", "şu", "o", "da", "de", "ki", "ben", "sen", "biz",
                 "diye", "gibi", "için", "ama", "fakat", "çok", "en", "daha", "ne", "nasıl",
                 "var", "yok", "olan", "olan", "diye", "oradan", "başlasın", "çıkar", "kısım",
                 "transcript", "içerisinde"}
    prompt_words = [w.lower().strip(".,!?\"'") for w in user_prompt.split()]
    search_words = [w for w in prompt_words if w not in stopwords and len(w) > 3]

    if not search_words:
        return seg_start

    # GPT'nin bölgesi etrafında ±window saniye — kelimeleri zaman sırasına göre sırala
    region = sorted(
        [w for w in word_segments if seg_start - window <= w["start"] <= seg_start + window],
        key=lambda w: w["start"]
    )

    # Her arama kelimesi için region'da eşleşme ara
    # En erken eşleşmeyi değil, seg_start'a en yakın olanı döndür
    best = None
    for search in search_words[:4]:
        for w in region:
            word_clean = w["text"].lower().strip(".,!?\"'")
            if word_clean == search or word_clean.startswith(search[:5]):
                dist = abs(w["start"] - seg_start)
                if best is None or dist < best[1]:
                    best = (w["start"], dist)
                break  # Bu search için ilk eşleşmeyi al, sonrakine geç

    return best[0] if best else seg_start


def _snap_to_sentence_end(seg_end, word_segments, lookahead=15.0):
    """
    GPT'nin seçtiği end_time'dan ileriye bakarak en yakın cümle sonunu bul.
    .!? ile biten kelimeyi bulunca orada kes.
    """
    sorted_words = sorted(word_segments, key=lambda w: w["start"])
    window = [w for w in sorted_words if w["start"] >= seg_end - 2.0 and w["start"] <= seg_end + lookahead]

    for w in window:
        if w["text"].rstrip().rstrip("\"'»").endswith((".", "!", "?", "…")):
            return w["end"]

    return seg_end


def process_short(video_path, seg, all_segments, word_segments, index, session_id, short_duration, user_prompt=None):
    """Crop, add subtitles, and save a single short."""
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    start = seg["start_time"]
    # GPT'nin transcript'indeki son kelimeyi bul, word_cache'de o kelimenin end zamanını kullan
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
    output_path = os.path.join(OUTPUT_FOLDER, f"short_{index}_{session_id}.mp4")
    add_subtitles(cropped_path, sub_segments, start, output_path)

    # Cleanup temp file
    if os.path.exists(cropped_path):
        os.remove(cropped_path)

    print(f"  💾 Kaydedildi: {output_path}\n")
    return output_path


LAST_VIDEO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_video.json")


def _ask_with_dialog():
    """
    macOS native dialog ile kullanıcıdan açıklama al.
    Boş bırakılırsa None döner.
    """
    script = '''
    set result to display dialog "Videonun hangi kısımlarını istiyorsun?\n\nÖrnek: 'fiyatları açıkladığım an' veya 'motivasyon verdiğim kısım'\n\nBoş bırakırsan AI kendi seçer." ¬
        default answer "" ¬
        with title "AI Shorts Generator" ¬
        buttons {"İptal", "Tamam"} ¬
        default button "Tamam"
    if button returned of result is "Tamam" then
        return text returned of result
    else
        return ""
    end if
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=120
        )
        text = result.stdout.strip()
        return text if text else None
    except Exception:
        # Dialog açılamazsa terminale düş
        text = input("\n🎯 Hangi anları istediğini açıkla (boş = AI seçer): ").strip()
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


def ask_setup():
    """Interactively ask the user for input video."""
    print("\n" + "=" * 55)
    print("  🎬  AI YouTube Shorts Generator")
    print("=" * 55)

    num_shorts = DEFAULT_NUM_SHORTS
    last_path, last_yt = _load_last_video()

    if last_path and os.path.exists(last_path):
        print(f"\n📁 Son video: {last_path}")
        choice = input("  Aynı videoyu kullan? (Enter = evet, yeni yol gir = hayır): ").strip().strip('"')
        if choice == "":
            video_input = last_path
            youtube_url = last_yt
        elif os.path.exists(choice):
            video_input = choice
            youtube_url = None
        else:
            print(f"  ❌ Dosya bulunamadı: {choice}, son video kullanılıyor.")
            video_input = last_path
            youtube_url = last_yt
    else:
        while True:
            path = input("\n📁 Video dosyasının yolunu gir: ").strip().strip('"')
            if os.path.exists(path):
                video_input = path
                youtube_url = None
                break
            print(f"  ❌ Dosya bulunamadı: {path}")

    user_prompt = _ask_with_dialog()
    if user_prompt:
        print(f"  📝 Açıklama alındı: {user_prompt}")
    else:
        print("  🤖 Açıklama girilmedi — AI kendi seçecek.")

    return video_input, youtube_url, user_prompt or None, num_shorts


def main():
    parser = argparse.ArgumentParser(
        description="AI YouTube Shorts Generator — Viral short videolar üret"
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="GPT seçimlerini otomatik onayla (batch mod)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=DEFAULT_SHORT_DURATION,
        help=f"Her short'un hedef süresi saniye cinsinden (varsayılan: {DEFAULT_SHORT_DURATION})"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Transkript cache'ini yoksay, yeniden transkript et"
    )
    args = parser.parse_args()

    # --- Interaktif kurulum ---
    video_input, youtube_url, user_prompt, num_shorts = ask_setup()

    session_id = str(uuid.uuid4())[:8]

    video_path = video_input
    _save_last_video(video_path, youtube_url)

    print(f"\n📹 Video: {video_path}")
    duration = get_video_duration(video_path)
    print(f"⏱  Toplam süre: {duration:.0f}s ({duration / 60:.1f} dakika)")

    # --- Transcription ---
    use_cache = not args.no_cache
    segments = transcribe(video_path, use_cache=use_cache, youtube_url=youtube_url)
    print(f"📝 {len(segments)} transkript segmenti")

    # --- Word-level timing (Whisper) ---
    word_segments = get_word_timed_segments(video_path, segments)

    # --- Generate Shorts ---
    produced = 0
    attempts = 0
    max_attempts = num_shorts * 4
    excluded_ranges = []

    print(f"\n🎯 Hedef: {num_shorts} short × {args.duration}s\n")

    while produced < num_shorts and attempts < max_attempts:
        attempts += 1

        print(f"🤖 GPT 3 bölüm seçiyor...")
        candidates = find_best_segment(
            segments,
            duration,
            short_duration=args.duration,
            excluded_ranges=excluded_ranges if excluded_ranges else None,
            user_prompt=user_prompt
        )

        if args.auto_approve:
            seg = candidates[0]
            print(f"  ✅ Otomatik onay: {seg['start_time']:.0f}s – {seg['end_time']:.0f}s")
        else:
            seg = pick_segment(candidates)

        if seg == "regenerate":
            print("  🔄 Yeniden seçiliyor...\n")
            continue
        elif seg is None:
            print("  ❌ İptal edildi.")
            break

        print(f"\n⚙️  Short işleniyor...")
        process_short(video_path, seg, segments, word_segments, produced + 1, session_id, args.duration, user_prompt)

        excluded_ranges.append((seg["start_time"], seg["end_time"]))
        produced += 1

    print(f"\n🎉 Tamamlandı! {produced} short '{OUTPUT_FOLDER}/' klasörüne kaydedildi.")
    if produced > 0:
        print(f"   Session ID: {session_id}")


if __name__ == "__main__":
    main()
