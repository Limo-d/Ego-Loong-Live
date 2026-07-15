#!/usr/bin/env python3
"""Re-encode RGB locally on the device before it crosses a wireless link."""
from __future__ import annotations

import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage


class LowLatencyRgbRepublisher(Node):
    def __init__(self) -> None:
        super().__init__("rgb_low_latency_republisher")
        self.declare_parameter(
            "input_topic", "/factor_perception/rgb/image_rect/compressed"
        )
        self.declare_parameter(
            "output_topic", "/factor_perception/rgb/image_rect/compressed_low_latency"
        )
        self.declare_parameter("jpeg_quality", 65)

        input_topic = str(self.get_parameter("input_topic").value)
        output_topic = str(self.get_parameter("output_topic").value)
        self.quality = max(1, min(100, int(self.get_parameter("jpeg_quality").value)))
        self.frames = 0
        self.input_bytes = 0
        self.output_bytes = 0
        self.processing_seconds = 0.0

        # Live preview prioritizes freshness over guaranteed delivery.
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.publisher = self.create_publisher(CompressedImage, output_topic, qos)
        self.subscription = self.create_subscription(
            CompressedImage, input_topic, self._on_image, qos
        )
        cv2.setNumThreads(1)
        self.get_logger().info(
            f"Low-latency RGB: {input_topic} -> {output_topic}, JPEG quality {self.quality}"
        )

    def _on_image(self, message: CompressedImage) -> None:
        started = time.perf_counter()
        source = np.frombuffer(message.data, dtype=np.uint8)
        image = cv2.imdecode(source, cv2.IMREAD_COLOR)
        if image is None:
            self.get_logger().error("Unable to decode incoming JPEG")
            return
        ok, encoded = cv2.imencode(
            ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self.quality]
        )
        if not ok:
            self.get_logger().error("Unable to encode low-latency JPEG")
            return

        output = CompressedImage()
        output.header = message.header
        output.format = "jpeg"
        output.data = encoded.tobytes()
        self.publisher.publish(output)

        self.frames += 1
        self.input_bytes += len(message.data)
        self.output_bytes += len(output.data)
        self.processing_seconds += time.perf_counter() - started
        if self.frames % 300 == 0:
            self.get_logger().info(
                "frames=%d input=%.1fKB output=%.1fKB processing=%.2fms"
                % (
                    self.frames,
                    self.input_bytes / self.frames / 1024,
                    self.output_bytes / self.frames / 1024,
                    self.processing_seconds / self.frames * 1000,
                )
            )


def main() -> None:
    rclpy.init()
    node = LowLatencyRgbRepublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
