"""ROS image conversion and JPEG encoding without cropping."""
from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

import numpy as np

try:
    import cv2
except ImportError:  # The lean Docker image uses Pillow instead of full OpenCV.
    cv2 = None

try:
    from PIL import Image as PillowImage
except ImportError:
    PillowImage = None


def _decode_compressed(data: bytes) -> np.ndarray:
    if cv2 is not None:
        encoded = np.frombuffer(data, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is not None:
            return image
    if PillowImage is not None:
        with PillowImage.open(BytesIO(data)) as decoded:
            rgb = np.asarray(decoded.convert("RGB"), dtype=np.uint8)
        return np.ascontiguousarray(rgb[:, :, ::-1])
    raise ValueError("Failed to decode image; install OpenCV or Pillow")


def _encode_jpeg(image: np.ndarray, quality: int) -> bytes:
    if cv2 is not None:
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok:
            return encoded.tobytes()
    if PillowImage is not None:
        output = BytesIO()
        rgb = np.ascontiguousarray(image[:, :, ::-1])
        PillowImage.fromarray(rgb, mode="RGB").save(output, format="JPEG", quality=quality)
        return output.getvalue()
    raise ValueError("JPEG encoding failed; install OpenCV or Pillow")


class ImageProcessor:
    def __init__(self, config: dict[str, Any]) -> None:
        self.quality = max(1, min(100, int(config.get("jpeg_quality", 85))))
        self.passthrough_compressed = bool(config.get("passthrough_compressed", False))
        self.allow_crop = bool(config.get("allow_crop", False))
        if self.allow_crop:
            raise ValueError("Ego-Loong Live forbids RGB cropping; rgb.allow_crop must be false")

    def process_compressed(self, item: dict[str, Any]) -> dict[str, Any]:
        image = _decode_compressed(item["data"])
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
                image = np.ascontiguousarray(image[:, :, ::-1])
        elif encoding in {"bgra8", "rgba8"}:
            image = rows[:, :width * 4].reshape(height, width, 4)
            image = image[:, :, :3]
            if encoding == "rgba8":
                image = image[:, :, ::-1]
            image = np.ascontiguousarray(image)
        elif encoding in {"mono8", "8uc1"}:
            image = np.repeat(rows[:, :width, np.newaxis], 3, axis=2)
        else:
            raise ValueError(f"Unsupported ROS Image encoding: {encoding}")
        return self.process_array(image, original_format=encoding, frame_id=item.get("frame_id"))

    def process_array(self, image: np.ndarray, original_format: str = "bgr8", frame_id: str | None = None) -> dict[str, Any]:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"Expected BGR image HxWx3, got {image.shape}")
        # No resize, ROI or geometry transform is performed.
        encoded = _encode_jpeg(image, self.quality)
        height, width = image.shape[:2]
        return {
            "jpeg": base64.b64encode(encoded).decode("ascii"),
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
