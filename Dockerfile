FROM python:3.11-slim-bullseye

# System dependencies: ffmpeg + OpenCV + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    xz-utils \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Static ffmpeg binary — no apt dependency hell
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then FFMPEG_ARCH="arm64"; else FFMPEG_ARCH="amd64"; fi && \
    curl -fsSL "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-${FFMPEG_ARCH}-static.tar.xz" \
    -o /tmp/ffmpeg.tar.xz \
    && tar -xf /tmp/ffmpeg.tar.xz -C /tmp \
    && mv /tmp/ffmpeg-*-${FFMPEG_ARCH}-static/ffmpeg /usr/local/bin/ \
    && mv /tmp/ffmpeg-*-${FFMPEG_ARCH}-static/ffprobe /usr/local/bin/ \
    && rm -rf /tmp/ffmpeg*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and font
COPY Components/ ./Components/
COPY main.py .
COPY Montserrat-ExtraBold.ttf .

# Output folder
RUN mkdir -p shorts

CMD ["python", "main.py", "--auto-approve"]
