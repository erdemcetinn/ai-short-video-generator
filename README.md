# AI Short Video Generator

Automatically extracts viral short clips from long videos using AI — transcription, viral scoring, face-aware crop, and word-level subtitles.

## How it works

```
Video (local file or YouTube URL)
        │
        ▼
  Transcription  ──  AssemblyAI (word-level timestamps, auto language detection)
        │             + GPT-4o transcript correction
        ▼
  Segment Selection  ──  GPT-4o viral scoring (hook, power words, emotional arc)
        │                 OR user-described segment ("the part where I explain X")
        ▼
  Face-Aware Crop  ──  OpenCV face detection + optical flow → 9:16 via ffmpeg
        │
        ▼
  Subtitles  ──  Word-by-word highlight (Montserrat ExtraBold, active word in yellow)
        │
        ▼
  shorts/{output}.mp4
```

## Setup

**Requirements:** Python 3.9+, ffmpeg

```bash
# 1. Clone
git clone https://github.com/erdemcetinn/ai-short-video-generator
cd ai-short-video-generator

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install ffmpeg
brew install ffmpeg        # macOS
# apt install ffmpeg       # Ubuntu

# 4. Add API keys
cp .env.example .env
# Edit .env with your keys
```

**.env:**
```
OPENAI_API_KEY=sk-...
ASSEMBLYAI_API_KEY=...
```

**Optional — better subtitles:**
Install Montserrat ExtraBold font. On macOS, place it at `~/Library/Fonts/Montserrat-ExtraBold.ttf`. Falls back to Impact if not found.

---

## Usage

```bash
python main.py
```

### Step 1 — Video source

A native dialog asks you to choose:
- **Download from YouTube** → paste a YouTube URL, video downloads automatically
- **Local File** → opens a file picker (or type the path manually)

On subsequent runs, you can reuse the last video or pick a new one.

### Step 2 — Describe what you want (optional)

A GUI window appears asking which part of the video to turn into a short.

- **Describe a moment** → e.g. `"the part where I explain the pricing"` — GPT finds it in the transcript
- **Leave it blank** → GPT auto-selects the most viral segment using a scoring rubric

### Step 3 — Pick a segment

GPT suggests 3 candidates ranked by viral score:

```
[1]  142s – 198s  (56s)  🔥 Viral: 87/100
     Why: Starts with a counterintuitive claim, strong punchline at the end...
     Transcript: "Nobody ever says this but..."

[2]  ...
[3]  ...

Pick (1/2/3) or [Y] regenerate, [C] cancel:
```

- `1` / `2` / `3` → select that segment
- `Y` → regenerate new suggestions
- `C` → cancel

### Step 4 — Output

Saved to `shorts/short_1_{session_id}.mp4`.

---

## CLI Options

```bash
# Auto-approve best segment without interactive selection
python main.py --auto-approve

# Custom clip duration (default: 60s)
python main.py --duration 45

# Force re-transcribe, ignore cache
python main.py --no-cache
```

---

## Key Features

**Per-video caching**
Each video gets its own cache files (`transcript_cache_{name}.json`, `word_cache_{name}.json`). Re-running on the same video skips all API calls.

**Auto language detection**
AssemblyAI's `universal-2` model detects the spoken language automatically — no hardcoded language setting needed.

**Two-pass transcription**
AssemblyAI handles word-level timing, then GPT-4o runs a correction pass to fix transcription errors (misheard words, wrong spellings) while preserving all timestamps. This improves both subtitle accuracy and segment selection quality.

**Viral scoring rubric**
GPT-4o scores segments across 5 dimensions:

| Dimension | Weight |
|-----------|--------|
| Power hook (first 3 seconds) | 25% |
| Power words & emotional triggers | 25% |
| Emotional arc & tension | 20% |
| Standalone completeness | 15% |
| Retention signal (last 5 seconds) | 15% |

**Smart cropping**
Face detection (OpenCV Haar cascade) centers the crop on the speaker. Falls back to optical flow for screen recordings or multi-person shots. Output: 1080×1920 (9:16).

**Sentence-aware cutting**
Snaps start/end times to natural speech boundaries — never cuts mid-sentence.

**Word-level subtitles**
Groups words by speech pauses (max 3 per group), highlights the active word in yellow, auto-scales font to fit screen width.

---

## Project Structure

### Local

```
.
├── main.py                    # Entry point and orchestration
├── dialog_helper.py           # Tkinter GUI for segment description input
├── requirements.txt
├── .env.example
├── Components/
│   ├── YoutubeDownloader.py   # yt-dlp wrapper
│   ├── Transcription.py       # AssemblyAI + GPT-4o correction + per-video caching
│   ├── LanguageTasks.py       # GPT-4o viral scoring + segment selection
│   ├── FaceCrop.py            # Face detection + optical flow + ffmpeg crop
│   ├── Subtitles.py           # Word-level subtitle rendering (PIL + MoviePy)
│   └── Edit.py                # ffprobe duration, audio extraction
└── shorts/                    # Output clips (gitignored)
```

### AWS (Cloud)

Everything above, plus:

```
.
├── Dockerfile                 # Container image for ECS Fargate
├── lambda_function.py         # Lambda: S3 event → starts ECS task
├── lambda_upload.py           # Lambda: generates presigned S3 upload URL
├── lambda_status.py           # Lambda: checks if output is ready
├── terraform/                 # Infrastructure as Code (Terraform)
│   ├── main.tf                # Provider config
│   ├── variables.tf           # Input variables (project_name, s3_bucket_name, region)
│   ├── outputs.tf             # Output values (API URL, ECR URL, website URL)
│   ├── s3.tf                  # S3 buckets (video + website)
│   ├── ecs.tf                 # ECS cluster, task definition, ECR repo
│   ├── lambda.tf              # Lambda functions
│   ├── api_gateway.tf         # API Gateway routes
│   ├── iam.tf                 # IAM roles and policies
│   ├── network.tf             # VPC, subnets, security groups
│   └── terraform.tfvars.example  # Template — copy to terraform.tfvars and fill in
└── website/
    └── index.html             # Static frontend (upload video, poll status, download)
```

## Tech Stack

### Local

| Layer | Technology |
|-------|-----------|
| Transcription | AssemblyAI (word timestamps, auto language detection) |
| AI | OpenAI GPT-4o (function calling, viral scoring) |
| Video processing | ffmpeg, MoviePy |
| Face detection | OpenCV (Haar cascade + optical flow) |
| Subtitles | PIL / Pillow |
| Download | yt-dlp |
| GUI | Tkinter (dark theme, runs as subprocess) |

### AWS (Cloud)

| Layer | Technology |
|-------|-----------|
| Compute | AWS ECS Fargate (serverless containers) |
| Storage | AWS S3 (video input/output + static website) |
| API | AWS API Gateway + Lambda (Python 3.13) |
| Container registry | AWS ECR |
| Secrets | AWS Secrets Manager |
| Logging | AWS CloudWatch |
| Infrastructure | Terraform |

---

## AWS Architecture

The project includes a fully serverless AWS pipeline so you can process videos from a web browser — no local Python environment needed.

```
[Website (S3 Static Hosting)]
  User selects video + types prompt → clicks "Generate Short"
        │
        ▼
[API Gateway → Lambda: ai-shorts-upload]
  Generates a presigned S3 URL
        │
        ▼
[S3 Bucket: input/]
  Browser uploads video directly to S3
  S3 stores prompt as object metadata
        │  (s3:ObjectCreated event)
        ▼
[Lambda: ai-shorts-trigger]
  Reads prompt from S3 metadata
  Starts ECS Fargate task with --prompt argument
        │
        ▼
[ECS Fargate Container (ECR image)]
  Downloads video from S3
  Runs full pipeline: transcribe → GPT → crop → subtitles
  Uploads result to S3: output/
        │
        ▼
[API Gateway → Lambda: ai-shorts-status]
  Website polls this endpoint
  Returns download URL (presigned) when output is ready
        │
        ▼
[Website]
  Shows "Download Short" button with presigned S3 URL
```

### AWS Resources

| Resource | Name | Purpose |
|----------|------|---------|
| S3 | `<s3_bucket_name>` | Video input/output storage |
| S3 | `<project_name>-website` | Static website hosting |
| ECR | `ai-shorts` | Docker image registry |
| ECS Cluster | `ai-shorts-cluster` | Fargate compute |
| ECS Task Definition | `ai-shorts-task` | Container config (2 vCPU, 4 GB) |
| Lambda | `ai-shorts-upload` | Generates presigned upload URL |
| Lambda | `ai-shorts-trigger` | S3 event → starts ECS task |
| Lambda | `ai-shorts-status` | Checks if output is ready |
| API Gateway | `ai-shorts-api` | HTTP endpoints for the website |
| Secrets Manager | `ai-shorts/api-keys` | Stores OPENAI and ASSEMBLYAI keys |
| CloudWatch | `/ecs/ai-shorts` | Container logs |

All infrastructure is defined in `terraform/` and managed with Terraform.

---

## Deploy to AWS

### Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.0
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configured (`aws configure`)
- [Docker](https://docs.docker.com/get-docker/) running locally

### Step 1 — Choose your project name

> ⚠️ **This is the most important decision before you deploy.**
>
> `project_name` is used as the prefix for **every AWS resource** that Terraform creates — ECS cluster, Lambda functions, IAM roles, S3 buckets, API Gateway, CloudWatch log groups, and Secrets Manager path. Choose it once and keep it consistent throughout all steps below.
>
> Example: `project_name = "ai-shorts-john"` creates:
> - S3 buckets: `ai-shorts-john` and `ai-shorts-john-website`
> - Lambda functions: `ai-shorts-john-upload`, `ai-shorts-john-trigger`, `ai-shorts-john-status`
> - ECS cluster: `ai-shorts-john-cluster`
> - Secrets Manager: `ai-shorts-john/api-keys`
> - ...and so on for every resource
>
> S3 bucket names must be **globally unique** across all AWS accounts — add your name or a unique suffix.

Pick your `project_name` now, then use it consistently in every step below.

### Step 2 — Store your API keys in Secrets Manager

Replace `<project_name>` with the value you chose above:

```bash
aws secretsmanager create-secret \
  --name <project_name>/api-keys \
  --region us-east-1 \
  --secret-string '{"OPENAI_API_KEY":"sk-...","ASSEMBLYAI_API_KEY":"..."}'
```

> This only needs to be done once. Terraform does not manage this secret so it won't be destroyed by `terraform destroy`.

### Step 3 — Provision infrastructure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your chosen `project_name`:

```hcl
project_name   = "ai-shorts-yourname"   # prefix for ALL AWS resources — must match Step 2
s3_bucket_name = "ai-shorts-yourname"   # main bucket for video input/output (must be globally unique)
aws_region     = "us-east-1"
```

Then apply:

```bash
terraform init
terraform apply
```

Take note of the outputs — you'll need them in the next steps:

```
api_gateway_url     = "https://<id>.execute-api.us-east-1.amazonaws.com/"
ecr_repository_url  = "<account>.dkr.ecr.us-east-1.amazonaws.com/ai-shorts"
website_bucket_name = "<project_name>-website"
website_url         = "http://<project_name>-website.s3-website-us-east-1.amazonaws.com"
```

### Step 4 — Build and push the Docker image

```bash
# Login to ECR (replace <account> with your AWS account ID)
docker login --username AWS \
  --password $(aws ecr get-login-password --region us-east-1) \
  <account>.dkr.ecr.us-east-1.amazonaws.com

# Build (--platform linux/amd64 is required — ECS Fargate runs on amd64,
# even if you are building on an Apple Silicon Mac)
cd ..   # back to project root
docker buildx build --platform linux/amd64 --no-cache -t ai-shorts .

# Tag
docker tag ai-shorts:latest <ecr_repository_url>:latest

# Push
docker push <ecr_repository_url>:latest
```

### Step 5 — Update the website with your API Gateway URL

Open `website/index.html` and find lines 307–308:

```javascript
const API_URL    = "https://<your-api-id>.execute-api.us-east-1.amazonaws.com/upload";
const STATUS_URL = "https://<your-api-id>.execute-api.us-east-1.amazonaws.com/status";
```

Replace `<your-api-id>` with the ID from your `api_gateway_url` terraform output.
The base URL ends with `/` — append `upload` and `status` as shown above.

For example, if your `api_gateway_url` is `https://abc123xyz.execute-api.us-east-1.amazonaws.com/`:

```javascript
const API_URL    = "https://abc123xyz.execute-api.us-east-1.amazonaws.com/upload";
const STATUS_URL = "https://abc123xyz.execute-api.us-east-1.amazonaws.com/status";
```

### Step 6 — Upload the website to S3

Terraform already configured S3 static website hosting and public access permissions — you just need to upload the file.

Replace `<project_name>` with the value you set in `terraform.tfvars`:

```bash
aws s3 cp website/index.html s3://<project_name>-website/index.html
```

### Step 7 — Open the website

Replace `<project_name>` with the value you set in `terraform.tfvars`:

```
http://<project_name>-website.s3-website-us-east-1.amazonaws.com
```

Select a video, enter an optional prompt, click **Generate Short**. The page polls for status and shows a download button when the short is ready.

---

### Teardown

```bash
cd terraform
terraform destroy
```

This removes all AWS resources except the Secrets Manager secret (created manually in Step 1).

To also delete the secret:

```bash
aws secretsmanager delete-secret --secret-id <project_name>/api-keys --force-delete-without-recovery
```
