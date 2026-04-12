import os
import json
from openai import OpenAI


def _find_by_user_prompt(user_prompt, segments, video_duration, excluded_note, client):
    """Find the segment matching the user's description and return 3 candidates."""
    transcript_text = ""
    for seg in segments:
        transcript_text += f"[{seg['start']:.1f}s - {seg['end']:.1f}s]: {seg['text']}\n"

    candidate_schema = {
        "type": "object",
        "properties": {
            "start_time": {"type": "number", "description": "Start timestamp of the selected segment — must match [X.Xs] value from the transcript"},
            "end_time": {"type": "number", "description": "End timestamp of the selected segment — must match [X.Xs] value from the transcript"},
            "viral_score": {"type": "number", "description": "0-100"},
            "hook_score": {"type": "number", "description": "0-100"},
            "reason": {"type": "string", "description": "Why you selected this segment"},
            "transcript": {"type": "string", "description": "Full text of the selected segment from start_time to end_time"}
        },
        "required": ["start_time", "end_time", "viral_score", "hook_score", "reason", "transcript"]
    }

    functions = [{
        "name": "select_highlights",
        "description": "Suggest 3 different segments",
        "parameters": {
            "type": "object",
            "properties": {
                "candidate_1": {**candidate_schema, "description": "Best option"},
                "candidate_2": {**candidate_schema, "description": "Second option"},
                "candidate_3": {**candidate_schema, "description": "Third option"},
            },
            "required": ["candidate_1", "candidate_2", "candidate_3"]
        }
    }]

    prompt = f"""You are a video editor. The following transcript is from a YouTube video.

The user wants: "{user_prompt}"

Read the transcript, understand the user's request, and suggest the 3 best segments for a YouTube Short.
Don't just follow rules — use your judgement. Think about which segment would have the most impact, deliver the strongest message, and make the best short.

IMPORTANT:
- Use the segment's start timestamp from the transcript as start_time (first number in square brackets)
- Use the segment's end timestamp from the transcript as end_time (second number in square brackets)
- Write ALL words from start_time to end_time in the transcript field
{excluded_note}
Transcript:
{transcript_text}"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        functions=functions,
        function_call={"name": "select_highlights"},
        temperature=0.3
    )

    raw = json.loads(response.choices[0].message.function_call.arguments)
    candidates = [raw["candidate_1"], raw["candidate_2"], raw["candidate_3"]]
    for c in candidates:
        if c["end_time"] > video_duration:
            c["end_time"] = video_duration
        if c["start_time"] < 0:
            c["start_time"] = 0
    return candidates


def find_best_segment(segments, video_duration, short_duration=60, excluded_ranges=None, user_prompt=None):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    transcript_text = ""
    for seg in segments:
        transcript_text += f"[{seg['start']:.1f}s - {seg['end']:.1f}s]: {seg['text']}\n"

    excluded_note = ""
    if excluded_ranges:
        ranges_str = ", ".join(f"{s:.0f}s-{e:.0f}s" for s, e in excluded_ranges)
        excluded_note = f"\nDo NOT use these time ranges (already used): {ranges_str}\n"


    candidate_schema = {
        "type": "object",
        "properties": {
            "start_time": {"type": "number", "description": "Start time in seconds — must align with a natural sentence beginning"},
            "end_time": {"type": "number", "description": "End time in seconds — must align with a natural sentence ending or long pause"},
            "viral_score": {"type": "number", "description": "Viral potential score 0-100"},
            "hook_score": {"type": "number", "description": "How strong the opening hook is 0-100"},
            "reason": {"type": "string", "description": "Specific reason based on actual content — quote the opening AND closing words"},
            "transcript": {"type": "string", "description": "Full transcript text of the selected segment"}
        },
        "required": ["start_time", "end_time", "viral_score", "hook_score", "reason", "transcript"]
    }

    functions = [
        {
            "name": "select_highlights",
            "description": "Select the 3 most viral-worthy segments for YouTube Shorts, ranked best to worst",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_1": {**candidate_schema, "description": "Best segment (highest viral score)"},
                    "candidate_2": {**candidate_schema, "description": "Second best segment"},
                    "candidate_3": {**candidate_schema, "description": "Third best segment"},
                },
                "required": ["candidate_1", "candidate_2", "candidate_3"]
            }
        }
    ]

    if user_prompt:
        return _find_by_user_prompt(user_prompt, segments, video_duration, excluded_note, client)

    prompt = f"""You are an expert viral content analyst specialized in Turkish YouTube Shorts and TikTok. You have reverse-engineered what makes content go viral for Turkish-speaking audiences.

Your task: Find the single BEST {short_duration}-second segment from this transcript that would perform like a top 1% viral short.

═══════════════════════════════════════
VIRAL SCORING SYSTEM (Total: 100 pts)
═══════════════════════════════════════

1. POWER HOOK (0-25 pts) — The first 3 seconds must STOP the scroll
   +25: Starts with a shocking revelation, counterintuitive claim, or direct challenge ("Yanlış biliyorsunuz", "Kimse bunu söylemez ama", "X yıldır bunu yapıyorsanız...")
   +20: Starts with a compelling question that triggers self-doubt or curiosity
   +15: Starts with a bold personal story opener ("O gün hayatım değişti", "İnanamadım")
   +5: Generic topic intro — penalize heavily
   +0: Mid-sentence start, filler words, intro/outro — DISQUALIFY

2. POWER WORDS & EMOTIONAL TRIGGERS (0-25 pts)
   Turkish viral power words — each one adds points:
   • Shock/Surprise: asla, hiç, inanamadım, şok, korkunç, dehşet, gerçek şu ki, yanlış
   • Urgency/Fear: dikkat, tehlike, kaçırıyorsunuz, son fırsat, artık geç
   • Curiosity gap: sır, kimse bilmiyor, açıklıyorum, işte neden, fark ettim ki
   • Social proof/authority: herkes, milyonlar, araştırmalar gösteriyor, kanıtlandı
   • Identity/Tribe: eğer sen de, bizim gibi, Türk, gençler, girişimciler
   Segments with 3+ power words score maximum. Zero power words = 0 pts.

3. EMOTIONAL ARC & TENSION (0-20 pts)
   +20: Has a clear tension → revelation structure within the segment
   +15: Builds curiosity then delivers a satisfying answer
   +10: Single strong emotional peak (anger, inspiration, humor, or disbelief)
   +5: Flat emotional delivery — avoid
   +0: Dry information, listing facts with no emotion

4. STANDALONE COMPLETENESS (0-15 pts)
   +15: Viewer gets a complete, satisfying idea — no "watch the full video" needed
   +10: Mostly complete with a small cliffhanger (acceptable)
   +5: Requires context from other parts — bad for Shorts
   +0: Mid-thought, incomplete argument, or just a transition

5. RETENTION SIGNAL (0-15 pts)
   +15: Has a payoff/punchline/reveal in the LAST 5 seconds — keeps viewers watching till end
   +10: Ends on a strong statement or call-to-action
   +5: Ends on a neutral statement
   +0: Trails off, unfinished thought, or ends abruptly

═══════════════════════════════════════
WHAT OPUS CLIP LOOKS FOR (apply these):
═══════════════════════════════════════
✓ "Pattern interrupt" moments — sudden topic shifts or surprising statements
✓ Sentences starting with "ama", "fakat", "oysa ki", "aslında", "işte tam burada"
✓ Personal vulnerability or confession ("İtiraf etmeliyim ki", "Daha önce ben de")
✓ Specific numbers/stats with shock value ("% 90", "sadece 3 günde", "10 milyon")
✓ Direct audience address ("Siz de bunu yapıyorsanız", "Bunu okuyan herkes")
✓ Controversy or contrarian takes ("Motivasyon konuşmaları işe yaramaz", "Para mutluluğu satın alır")

═══════════════════════════════════════
DISQUALIFYING FACTORS (score = 0):
═══════════════════════════════════════
✗ Starts with "Bugün size", "Merhaba", "Hoş geldiniz", "Bu videoda"
✗ Channel/video promotion or sponsor mentions
✗ Pure information listing with no emotional hook
✗ Segment is mostly filler, uhh/mm sounds, or transitions
✗ Starts in the middle of a list item or mid-argument without context

HOW TO FIND THE PERFECT CLIP (follow this order):
STEP 1 — Find all "complete thought units" in the transcript. A complete thought is a story, argument, or idea that has a clear beginning AND a satisfying conclusion. It does NOT end mid-argument or mid-story.
STEP 2 — Among those complete thoughts, score each one using the viral rubric above.
STEP 3 — For the highest-scoring complete thought, find the strongest hook sentence within or just before it to use as start_time.
STEP 4 — end_time = the timestamp AFTER the last word of the conclusion of that thought.

STRICT RULES:
- end_time MUST be the natural end of a complete idea — if the speaker is mid-sentence or mid-argument at end_time, you chose wrong
- start_time MUST be the timestamp of the first word of a grammatically complete, self-contained sentence
- Read the transcript text at your chosen start_time and ask yourself: "Could this sentence stand alone as the opening of a speech?" If NO — if it continues a previous thought, references something said before, or feels like a mid-sentence — move forward until you find a proper sentence opener
- You understand the grammar of the video's language: use that knowledge to identify real sentence boundaries, not just punctuation
- Duration: the viewer should feel they received a complete, meaningful message when the clip ends. Let the content determine the length.
- start_time >= 0, end_time <= {video_duration:.0f}
- DO NOT pick the first segment of the video unless it's truly exceptional
- The 'reason' field must quote the ACTUAL opening AND closing words to prove the thought is complete
- viral_score must honestly reflect the scoring rubric above
{excluded_note}
Transcript:
{transcript_text}"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        functions=functions,
        function_call={"name": "select_highlights"},
        temperature=0.3
    )

    raw = json.loads(response.choices[0].message.function_call.arguments)
    candidates = [raw["candidate_1"], raw["candidate_2"], raw["candidate_3"]]

    for c in candidates:
        if c["end_time"] > video_duration:
            c["end_time"] = video_duration
        if c["start_time"] < 0:
            c["start_time"] = 0

    return candidates
