import cv2
import numpy as np
import subprocess
import os


def detect_face_position(video_path, num_frames=30):
    """Detect face horizontal position from first N frames. Returns median x center."""
    cap = cv2.VideoCapture(video_path)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    face_x_positions = []
    frame_count = 0

    while frame_count < num_frames:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=8, minSize=(30, 30)
        )

        if len(faces) > 0:
            largest = max(faces, key=lambda f: f[2] * f[3])
            x, y, w, h = largest
            face_x_positions.append(x + w // 2)

        frame_count += 1

    cap.release()

    if face_x_positions:
        return int(np.median(face_x_positions))
    return None


def get_motion_center(video_path):
    """Use optical flow to find horizontal center of motion."""
    cap = cv2.VideoCapture(video_path)
    fps = max(1, cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    ret, prev_frame = cap.read()
    if not ret:
        cap.release()
        return width // 2

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

    motion_centers = []
    current_center = width // 2
    frame_idx = 0
    update_interval = int(fps)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % update_interval == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )

            magnitude = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
            motion_mask = magnitude > 2.0

            if motion_mask.any():
                col_motion = motion_mask.sum(axis=0).astype(float)
                total = col_motion.sum()
                if total > 0:
                    new_center = int(np.average(np.arange(width), weights=col_motion))
                    # Smooth: 90% old + 10% new
                    current_center = int(0.9 * current_center + 0.1 * new_center)
                    motion_centers.append(current_center)

            prev_gray = gray

        frame_idx += 1

    cap.release()

    if motion_centers:
        return int(np.median(motion_centers))
    return width // 2


def crop_to_vertical(input_path, output_path, start, end):
    """
    Crop video segment to 9:16 vertical format.
    Uses face detection for talking-head videos, optical flow for screen recordings.
    """
    cap = cv2.VideoCapture(input_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    target_width = int(height * 9 / 16)

    if target_width >= width:
        # Already narrow enough, just scale
        vf = f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
        crop_filter = vf
    else:
        print("🔍 Yüz tespiti yapılıyor...")
        face_x = detect_face_position(input_path)

        if face_x is not None:
            print(f"✅ Yüz tespit edildi (x={face_x})")
            crop_x = face_x + 60 - target_width // 2
        else:
            print("🎯 Yüz bulunamadı, hareket takibi kullanılıyor...")
            motion_x = get_motion_center(input_path)
            crop_x = motion_x - target_width // 2

        crop_x = max(0, min(crop_x, width - target_width))
        crop_filter = f"crop={target_width}:{height}:{crop_x}:0,scale=1080:1920"

    print(f"✂️  Kırpılıyor: {start}s - {end}s")
    subprocess.run([
        "ffmpeg", "-i", input_path,
        "-ss", str(start), "-to", str(end),
        "-vf", crop_filter,
        "-c:v", "libx264", "-c:a", "aac",
        "-y", output_path, "-loglevel", "quiet"
    ], check=True)
