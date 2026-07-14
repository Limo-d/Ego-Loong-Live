"""ROS image conversion and JPEG encoding without cropping."""
from __future__ import annotations

import base64
from typing import Any

import cv2
import numpy as np


class ImageProcessor:
    def __init__(self, config: dict[str, Any]) -> None:
        self.quality = max(1, min(100, int(config.get("jpeg_quality", 85))))
        self.passthrough_compressed = bool(config.get("passthrough_compressed", False))
        self.allow_crop = bool(config.get("allow_crop", False))
        if self.allow_crop:
            raise ValueError("Ego-Loong Live forbids RGB cropping; rgb.allow_crop must be false")

    def process_compressed(self, item: dict[str, Any]) -> dict[str, Any]:
        encoded = np.frombuffer(item["data"], dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Failed to decode sensor_msgs/CompressedImage")
        source_format = str(item.get("format", "compressed"))
        if not self.passthrough_compressed or ("jpeg" not in source_format.lower() and "jpg" not in source_format.lower()):
            return self.process_array(image, original_format=source_format, frame_id=item.get("frame_id"))
        height, width = image.shape[:2]
        return {
            "jpeg": base64.b64encode(item["data"]).decode("ascii"),
            "mime": "image/jpeg",
            "width": int(width),
            "height": int(height),
            "aspect_ratio": round(width / max(1, height), 6),
            "jpeg_quality": None,
            "original_format": source_format,
            "frame_id": item.get("frame_id"),
            "preserve_full_frame": True,
            "cropped": False,
        }

    def process_raw(self, item: dict[str, Any]) -> dict[str, Any]:
        height, width, step = int(item["height"]), int(item["width"]), int(item["step"])
        encoding = str(item.get("encoding", "bgr8")).lower()
        raw = np.frombuffer(item["data"], dtype=np.uint8)
        rows = raw.reshape(height, step)
        if encoding in {"bgr8", "rgb8"}:
            image = rows[:, :width * 3].reshape(height, width, 3)
            if encoding == "rgb8":
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        elif encoding in {"bgra8", "rgba8"}:
            image = rows[:, :width * 4].reshape(height, width, 4)
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR if encoding == "rgba8" else cv2.COLOR_BGRA2BGR)
        elif encoding in {"mono8", "8uc1"}:
            image = cv2.cvtColor(rows[:, :width], cv2.COLOR_GRAY2BGR)
        else:
            raise ValueError(f"Unsupported ROS Image encoding: {encoding}")
        return self.process_array(image, original_format=encoding, frame_id=item.get("frame_id"))

    def process_array(self, image: np.ndarray, original_format: str = "bgr8", frame_id: str | None = None) -> dict[str, Any]:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"Expected BGR image HxWx3, got {image.shape}")
        # No resize, ROI or geometry transform is performed.
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
        if not ok:
            raise ValueError("OpenCV JPEG encoding failed")
        height, width = image.shape[:2]
        return {
            "jpeg": base64.b64encode(encoded.tobytes()).decode("ascii"),
            "mime": "image/jpeg",
            "width": int(width),
            "height": int(height),
            "aspect_ratio": round(width / max(1, height), 6),
            "jpeg_quality": self.quality,
            "original_format": original_format,
            "frame_id": frame_id,
            "preserve_full_frame": True,
            "cropped": False,
        }

