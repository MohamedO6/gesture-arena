"""MediaPipe model lifecycle, hand readiness, and mirrored OpenCV video."""
from __future__ import annotations

import hashlib
import logging
import os
import ssl
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import av
import certifi
import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from streamlit_webrtc import VideoProcessorBase

from game import GESTURE_MAP, Observation
from runtime import SharedArena

LOGGER = logging.getLogger(__name__)
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task"
MODEL_PATH = Path(__file__).resolve().parent / "models" / "gesture_recognizer.task"
_DOWNLOAD_LOCK = threading.Lock()
# Normalized bounds: the palm center must be inside this upper-middle zone.
TARGET_ZONE = (0.18, 0.12, 0.82, 0.76)
CONNECTIONS = ((0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
               (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
               (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20))


class ModelLoadError(RuntimeError):
    pass


def _valid_model(path: Path) -> bool:
    try:
        return path.stat().st_size > 1_000_000 and zipfile.is_zipfile(path)
    except OSError:
        return False


def ensure_model(path: Path = MODEL_PATH) -> Path:
    """Download the versioned official task bundle atomically, once per process."""
    with _DOWNLOAD_LOCK:
        if _valid_model(path):
            return path
        temporary = path.with_suffix(f".{os.getpid()}.part")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "GestureArena/1.0"})
            with urllib.request.urlopen(request, timeout=30, context=ssl.create_default_context(cafile=certifi.where())) as response:
                size = 0
                with temporary.open("wb") as output:
                    while chunk := response.read(256 * 1024):
                        size += len(chunk)
                        if size > 32 * 1024 * 1024:
                            raise ValueError("Unexpected model size")
                        output.write(chunk)
            if not _valid_model(temporary):
                raise ValueError("The model download was incomplete")
            temporary.replace(path)
            LOGGER.info("Downloaded official model (%s)", hashlib.sha256(path.read_bytes()).hexdigest())
            return path
        except (OSError, urllib.error.URLError, ValueError) as exc:
            temporary.unlink(missing_ok=True)
            raise ModelLoadError(
                "The hand model couldn't be downloaded. Check your internet connection and retry. "
                "The app needs access to storage.googleapis.com and a writable models folder."
            ) from exc


class VisionModel:
    """One VIDEO-mode model per browser session; reused across reruns and restarts."""
    def __init__(self, model_path: Path | None = None) -> None:
        path = ensure_model() if model_path is None else model_path
        self._lock = threading.Lock()
        self._closed = False
        self._last_timestamp = -1
        try:
            options = vision.GestureRecognizerOptions(
                base_options=python.BaseOptions(model_asset_path=str(path)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=2,  # Detect extra hands so a round cannot silently accept one.
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._recognizer = vision.GestureRecognizer.create_from_options(options)
        except Exception as exc:
            raise ModelLoadError(
                "The hand model couldn't start. Use Python 3.12 or 3.13 on a supported 64-bit system, "
                "install the listed dependencies, then retry. See the README for Linux packages."
            ) from exc

    def recognize(self, rgb: np.ndarray, now: float):
        with self._lock:
            if self._closed:
                raise RuntimeError("The vision model is closed")
            timestamp = max(self._last_timestamp + 1, int(now * 1000))
            self._last_timestamp = timestamp
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
            return self._recognizer.recognize_for_video(image, timestamp)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._recognizer.close()
                self._closed = True


def hand_readiness(landmarks) -> tuple[bool, str]:
    """Use palm landmarks rather than fingertips, so all three moves fit equally."""
    palm = [landmarks[index] for index in (0, 5, 9, 13, 17)]
    x = sum(point.x for point in palm) / len(palm)
    y = sum(point.y for point in palm) / len(palm)
    left, top, right, bottom = TARGET_ZONE
    if y > bottom:
        return False, "Hand detected! Move your hand higher."
    if y < top:
        return False, "Hand detected! Move your hand a little lower."
    if not left <= x <= right:
        return False, "Hand detected! Move your hand toward the center."
    # A clipped hand is unreliable even if its palm center is in the zone.
    if any(not 0.02 <= p.x <= 0.98 or not 0.02 <= p.y <= 0.98 for p in landmarks):
        return False, "Keep your whole hand in view. Move a little farther back."
    return True, "You're ready! Make your move."


def classify_result(result, now: float) -> Observation:
    count = len(result.hand_landmarks)
    if count != 1:
        return Observation(now, hand_count=count)
    ready, hint = hand_readiness(result.hand_landmarks[0])
    category = result.gestures[0][0] if result.gestures and result.gestures[0] else None
    return Observation(now, hand_count=1, in_zone=ready,
                       move=GESTURE_MAP.get(category.category_name) if category else None,
                       confidence=float(category.score) if category else 0.0,
                       position_hint=hint)


def draw_overlay(bgr: np.ndarray, result, observation: Observation) -> np.ndarray:
    height, width = bgr.shape[:2]
    left, top, right, bottom = TARGET_ZONE
    x1, y1, x2, y2 = int(left * width), int(top * height), int(right * width), int(bottom * height)
    color = (94, 197, 34) if observation.in_zone and observation.hand_count == 1 else (122, 102, 73)
    # Quiet corner brackets keep the hand visible.
    for x, y, dx, dy in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
        cv2.line(bgr, (x, y), (x + dx * 24, y), color, 2, cv2.LINE_AA)
        cv2.line(bgr, (x, y), (x, y + dy * 24), color, 2, cv2.LINE_AA)
    for hand in result.hand_landmarks:
        points = [(int(p.x * width), int(p.y * height)) for p in hand]
        for start, end in CONNECTIONS:
            cv2.line(bgr, points[start], points[end], (94, 197, 34), 2, cv2.LINE_AA)
        for point in points:
            cv2.circle(bgr, point, 4, (238, 211, 34), -1, cv2.LINE_AA)
            cv2.circle(bgr, point, 4, (255, 245, 210), 1, cv2.LINE_AA)
    label = observation.move.value if observation.move and observation.hand_count == 1 and observation.in_zone else "KEEP ONE HAND IN THE ZONE"
    cv2.rectangle(bgr, (0, height - 38), (width, height), (26, 13, 8), -1)
    cv2.putText(bgr, label, (18, height - 13), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                (248, 250, 252), 1, cv2.LINE_AA)
    return bgr


class ArenaVideoProcessor(VideoProcessorBase):
    def __init__(self, model: VisionModel, shared: SharedArena) -> None:
        self._model = model
        self._shared = shared
        self._generation = shared.open_stream()
        self._processing_lock = threading.Lock()
        self._logged_error = False

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        # MediaPipe VIDEO timestamps and shared observations stay in frame order.
        with self._processing_lock:
            bgr = cv2.flip(frame.to_ndarray(format="bgr24"), 1)
            # Limit CPU and bandwidth while preserving the 4:3-ish camera aspect.
            if bgr.shape[1] > 640:
                bgr = cv2.resize(bgr, (640, round(bgr.shape[0] * 640 / bgr.shape[1])))
            try:
                result = self._model.recognize(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), time.monotonic())
                # Timestamp observations after inference; arrival freshness is measured here.
                observation = classify_result(result, time.monotonic())
                self._shared.publish(observation, self._generation)
                bgr = draw_overlay(bgr, result, observation)
                self._logged_error = False
            except Exception:
                if not self._logged_error:
                    LOGGER.exception("Camera frame processing failed")
                    self._logged_error = True
                self._shared.publish(Observation(time.monotonic(), error=
                    "Hand recognition paused. Stop and restart the camera. If it continues, reload the app."),
                    self._generation)
                cv2.putText(bgr, "VISION PAUSED - RESTART CAMERA", (16, 32),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 100, 255), 1, cv2.LINE_AA)
            return av.VideoFrame.from_ndarray(bgr, format="bgr24")

    def on_ended(self) -> None:
        self._shared.stream_ended(self._generation)
