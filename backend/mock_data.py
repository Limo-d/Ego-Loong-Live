"""Deterministic, smooth mock RGB/tactile/hand streams."""
from __future__ import annotations

import math
import threading
import time
from typing import Any

import numpy as np

try:
    import cv2
except ImportError:  # The lean Docker image renders mock frames with Pillow.
    cv2 = None

try:
    from PIL import Image as PillowImage
    from PIL import ImageDraw
except ImportError:
    PillowImage = None
    ImageDraw = None

from .data_store import DataStore
from .hand_pose_processor import HandPoseProcessor
from .image_processor import ImageProcessor
from .tactile_processor import TactileProcessor


def _quat_axis_angle(axis: tuple[float, float, float], angle: float) -> list[float]:
    vector = np.asarray(axis, dtype=np.float64)
    vector /= max(np.linalg.norm(vector), 1e-12)
    half = angle * 0.5
    return [math.cos(half), *(vector * math.sin(half)).tolist()]


class MockDataEngine(threading.Thread):
    def __init__(self, config: dict[str, Any], store: DataStore) -> None:
        super().__init__(daemon=True, name="ego-loong-mock")
        self.config = config
        self.store = store
        self.stop_event = threading.Event()
        self.image = ImageProcessor(config.get("rgb", {}))
        self.hand = HandPoseProcessor(config.get("hand", {}))
        self.tactile = {
            "left": TactileProcessor(config.get("tactile", {}), "left"),
            "right": TactileProcessor(config.get("tactile", {}), "right"),
        }
        self.start_time = time.monotonic()

    def _state27(self, elapsed: float, side: str) -> list[float]:
        phase = elapsed * 1.15 + (0.8 if side == "right" else 0.0)
        state = [0.0] * 27
        for finger in range(4):
            wave = 0.5 + 0.5 * math.sin(phase + finger * 0.32)
            base = finger * 4
            state[base] = 58.0 * wave
            state[base + 1] = (finger - 1.5) * 3.0 * math.sin(phase * 0.55)
            state[base + 2] = 76.0 * wave
            state[base + 3] = 52.0 * wave
        thumb_wave = 0.5 + 0.5 * math.sin(phase + 1.1)
        state[16:19] = [38.0 * thumb_wave, 24.0 * math.sin(phase * 0.7), 42.0 * thumb_wave]
        state[19:23] = _quat_axis_angle((0.2, 1.0, 0.2), 0.45 * math.sin(phase * 0.65))
        state[23:27] = _quat_axis_angle((0.0, 0.0, 1.0), 0.18 * math.sin(phase * 0.25))
        return state

    def _pressure(self, elapsed: float, side: str) -> list[float]:
        values = np.full(68, 10.0, dtype=np.float64)
        if elapsed < 1.0:
            return values.tolist()
        phase = elapsed * 1.3 + (1.4 if side == "right" else 0.0)
        centers = (2, 7, 11, 25 + int((math.sin(phase * 0.4) + 1) * 14))
        amplitudes = (45, 70, 38, 54)
        for center, amplitude in zip(centers, amplitudes):
            strength = amplitude * (0.5 + 0.5 * math.sin(phase + center * 0.17))
            for index in range(68):
                values[index] += strength * math.exp(-0.5 * ((index - center) / 2.2) ** 2)
        return values.tolist()

    def _rgb(self, elapsed: float) -> np.ndarray:
        width = int(self.config.get("rgb", {}).get("width", 960))
        height = int(self.config.get("rgb", {}).get("height", 540))
        x = np.linspace(0, 1, width, dtype=np.float32)
        y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
        image = np.empty((height, width, 3), dtype=np.uint8)
        image[..., 0] = np.clip(238 - 30 * y + 10 * np.sin(x * 8 + elapsed), 0, 255)
        image[..., 1] = np.clip(244 - 22 * y + 12 * x, 0, 255)
        image[..., 2] = np.clip(250 - 18 * x + 8 * np.cos(y * 7 + elapsed), 0, 255)
        cx = int(width * (0.5 + 0.28 * math.sin(elapsed * 0.55)))
        cy = int(height * (0.52 + 0.18 * math.cos(elapsed * 0.72)))
        if cv2 is not None:
            cv2.circle(image, (cx, cy), 54, (226, 159, 72), -1, cv2.LINE_AA)
            cv2.circle(image, (cx, cy), 35, (246, 223, 176), -1, cv2.LINE_AA)
            cv2.putText(image, "Ego-Loong Live / MOCK", (36, 58), cv2.FONT_HERSHEY_SIMPLEX, 1.05, (86, 107, 132), 2, cv2.LINE_AA)
            cv2.putText(image, f"{width} x {height}  |  t={elapsed:07.2f}s", (38, height - 38), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (83, 110, 139), 2, cv2.LINE_AA)
        elif PillowImage is not None and ImageDraw is not None:
            canvas = PillowImage.fromarray(np.ascontiguousarray(image[:, :, ::-1]))
            draw = ImageDraw.Draw(canvas)
            draw.ellipse((cx - 54, cy - 54, cx + 54, cy + 54), fill=(72, 159, 226))
            draw.ellipse((cx - 35, cy - 35, cx + 35, cy + 35), fill=(176, 223, 246))
            draw.text((36, 36), "Ego-Loong Live / MOCK", fill=(132, 107, 86))
            draw.text((38, height - 38), f"{width} x {height}  |  t={elapsed:07.2f}s", fill=(139, 110, 83))
            image = np.ascontiguousarray(np.asarray(canvas)[:, :, ::-1])
        return image

    def run(self) -> None:
        self.store.set_ros_state(initialized=False, error=None, topics=[], subscriptions=[], last_discovery=time.time())
        next_rgb = next_tactile = next_hand = time.monotonic()
        while not self.stop_event.is_set():
            now = time.monotonic()
            elapsed = now - self.start_time
            if now >= next_hand:
                for side in ("left", "right"):
                    pose = self.hand.process(self._state27(elapsed, side), side)
                    self.store.update(f"hand_pose_{side}", pose, time.time())
                next_hand += 1.0 / max(1.0, float(self.config.get("hand", {}).get("max_fps", 60)))
            if now >= next_tactile:
                for side in ("left", "right"):
                    payload = self.tactile[side].process(self._pressure(elapsed, side))
                    self.store.update(f"tactile_{side}", payload, time.time())
                next_tactile += 1.0 / max(1.0, float(self.config.get("tactile", {}).get("max_fps", 30)))
            if now >= next_rgb:
                payload = self.image.process_array(self._rgb(elapsed), original_format="mock_bgr8", frame_id="mock_camera")
                self.store.update("rgb", payload, time.time())
                next_rgb += 1.0 / max(1.0, float(self.config.get("rgb", {}).get("max_fps", 30)))
            time.sleep(0.001)

    def stop(self) -> None:
        self.stop_event.set()
        self.join(timeout=2.0)
