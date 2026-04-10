# AI YouTube Shorts Generator

Automatically extracts viral short clips from long YouTube videos using AI.

## What it does

1. **Downloads** a YouTube video (or takes a local file)
2. **Transcribes** speech with word-level timestamps via AssemblyAI
3. **Finds the best segment** using GPT-4o — either by your description or by viral scoring
4. **Crops to vertical (9:16)** with face detection and optical flow tracking
5. **Adds synchronized subtitles** with word-by-word highlight

## Architecture

```
YouTube URL / Local file
        │
        ▼
  YoutubeDownloader (yt-dlp)
        │
        ▼
  Transcription (AssemblyAI → word timestamps → GPT-4o correction)
        │
        ▼
  LanguageTasks (GPT-4o → viral scoring → 3 segment candidates)
        │
        ▼
  FaceCrop (OpenCV face detection + optical flow → 9:16 crop via ffmpeg)
        │
        ▼
  Subtitles (PIL word-level rendering → MoviePy composite)
        │
        ▼
  shorts/{output}.mp4
```

## Setup

```bash
# 1. Clone
git clone https://github.com/erdemcetinn/ai-shorts-generator
cd ai-shorts-generator

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install system dependencies
brew install ffmpeg          # macOS
# apt install ffmpeg         # Ubuntu

# 4. Add API keys
cp .env.example .env
# Edit .env and add your keys
```

**.env file:**
```
OPENAI_API_KEY=sk-...
ASSEMBLYAI_API_KEY=...
```

## Usage

```bash
# Interactive mode (recommended)
python main.py

# Auto-approve best segment (batch mode)
python main.py --auto-approve

# Custom clip duration (default: 60s)
python main.py --duration 45
```

**Interactive flow:**
1. Enter video path or press Enter to reuse last video
2. Describe what you want: *"the part where I explain pricing"* or leave blank for AI auto-select
3. GPT suggests 3 candidates with viral scores — pick one
4. Output saved to `shorts/`

## Key Features

- **Turkish language support** — AssemblyAI `universal-2` model + GPT-4o transcript correction
- **Viral scoring** — GPT-4o scores segments on hook strength, power words, emotional arc, retention
- **Smart crop** — face detection first, optical flow fallback for screen recordings
- **Sentence-aware cutting** — never cuts mid-sentence; snaps to natural speech boundaries
- **Word-level subtitles** — Montserrat ExtraBold, active word highlighted in yellow
- **Transcript cache** — re-running on same video skips API calls

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Transcription | AssemblyAI (word timestamps) |
| AI | OpenAI GPT-4o (function calling) |
| Video processing | ffmpeg, MoviePy |
| Face detection | OpenCV (Haar cascade + optical flow) |
| Subtitles | PIL / Pillow |
| Download | yt-dlp |

## Project Structure

```
.
├── main.py                  # Entry point, orchestration
├── requirements.txt
├── Components/
│   ├── YoutubeDownloader.py # yt-dlp wrapper
│   ├── Transcription.py     # AssemblyAI + GPT correction + caching
│   ├── LanguageTasks.py     # GPT-4o viral scoring + segment selection
│   ├── FaceCrop.py          # Face detection + optical flow + ffmpeg crop
│   ├── Subtitles.py         # Word-level subtitle rendering
│   └── Edit.py              # ffprobe duration, audio extraction
└── shorts/                  # Output clips (gitignored)
```
