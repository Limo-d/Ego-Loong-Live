"""ROS 2 subscriptions isolated from image/FK/WebSocket processing."""
from __future__ import annotations

import os
import threading
import time
from typing import Any

from .data_store import DataStore
from .hand_pose_processor import HandPoseProcessor
from .image_processor import ImageProcessor
from .tactile_processor import TactileProcessor


def _stamp_seconds(stamp: Any) -> float | None:
    if stamp is None:
        return None
    sec, nanosec = int(getattr(stamp, "sec", 0)), int(getattr(stamp, "nanosec", 0))
    value = sec + nanosec / 1e9
    return value if value > 0 else None


class LatestRosInput:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.rgb_revision = self.hand_revision = 0
        self.rgb: dict[str, Any] | None = None
        self.hand: dict[str, Any] | None = None

    def put_rgb(self, item: dict[str, Any]) -> None:
        with self.lock:
            self.rgb_revision += 1
            self.rgb = item

    def put_hand(self, item: dict[str, Any]) -> None:
        with self.lock:
            self.hand_revision += 1
            self.hand = item

    def snapshot(self) -> tuple[int, dict[str, Any] | None, int, dict[str, Any] | None]:
        with self.lock:
            return self.rgb_revision, self.rgb, self.hand_revision, self.hand


class RosBridge:
    def __init__(self, config: dict[str, Any], store: DataStore) -> None:
        self.config, self.store = config, store
        self.inputs = LatestRosInput()
        self.stop_event = threading.Event()
        self.ros_thread: threading.Thread | None = None
        self.worker_thread: threading.Thread | None = None
        self.node = None
        self.image = ImageProcessor(config.get("rgb", {}))
        self.hand_pose = HandPoseProcessor(config.get("hand", {}))
        self.tactile = {
            "left": TactileProcessor(config.get("tactile", {}), "left"),
            "right": TactileProcessor(config.get("tactile", {}), "right"),
        }

    def start(self) -> None:
        os.environ["ROS_DOMAIN_ID"] = str(self.config.get("ros", {}).get("domain_id", 0))
        self.worker_thread = threading.Thread(target=self._worker, daemon=True, name="ego-loong-process")
        self.ros_thread = threading.Thread(target=self._spin, daemon=True, name="ego-loong-ros")
        self.worker_thread.start()
        self.ros_thread.start()

    def _spin(self) -> None:
        try:
            import rclpy
            from rclpy.node import Node
            from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
            from sensor_msgs.msg import CompressedImage, Image
            from hand_frame.msg import HandFrame

            bridge = self
            rgb_cfg = self.config["topics"]["rgb"]
            hand_cfg = self.config["topics"]["hand"]

            class LiveNode(Node):
                def __init__(self) -> None:
                    super().__init__("ego_loong_live")
                    rgb_type = CompressedImage if rgb_cfg["type"] == "sensor_msgs/msg/CompressedImage" else Image
                    # RGB is a live preview, so stale frames are worse than
                    # dropped frames. A one-frame best-effort reader prevents
                    # Wi-Fi jitter from building a middleware backlog.
                    rgb_qos = QoSProfile(
                        depth=max(1, int(self.config_rgb_queue_depth)),
                        reliability=ReliabilityPolicy.BEST_EFFORT,
                        history=HistoryPolicy.KEEP_LAST,
                    )
                    self.create_subscription(rgb_type, rgb_cfg["name"], self.on_rgb, rgb_qos)
                    hand_qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST)
                    self.create_subscription(HandFrame, hand_cfg["name"], self.on_hand, hand_qos)

                @property
                def config_rgb_queue_depth(self) -> int:
                    return int(bridge.config.get("rgb", {}).get("queue_depth", 1))

                def on_rgb(self, msg: Any) -> None:
                    header = getattr(msg, "header", None)
                    item = {
                        "kind": "compressed" if isinstance(msg, CompressedImage) else "raw",
                        "data": bytes(msg.data),
                        "frame_id": str(getattr(header, "frame_id", "")),
                        "source_timestamp": _stamp_seconds(getattr(header, "stamp", None)),
                    }
                    if isinstance(msg, CompressedImage):
                        item["format"] = str(msg.format)
                    else:
                        item.update(height=int(msg.height), width=int(msg.width), encoding=str(msg.encoding), step=int(msg.step))
                    bridge.inputs.put_rgb(item)

                def on_hand(self, msg: Any) -> None:
                    bridge.inputs.put_hand({
                        "pressure_left": list(msg.pressure_left),
                        "pressure_right": list(msg.pressure_right),
                        "solve_state_left": list(msg.solve_state_left),
                        "solve_state_right": list(msg.solve_state_right),
                        "imu_stamp_left": _stamp_seconds(msg.imu_stamp_left),
                        "imu_stamp_right": _stamp_seconds(msg.imu_stamp_right),
                        "pressure_stamp_left": _stamp_seconds(msg.pressure_stamp_left),
                        "pressure_stamp_right": _stamp_seconds(msg.pressure_stamp_right),
                    })

            rclpy.init(args=None)
            self.node = LiveNode()
            subscriptions = [
                {"name": rgb_cfg["name"], "type": rgb_cfg["type"]},
                {"name": hand_cfg["name"], "type": hand_cfg["type"]},
            ]
            self.store.set_ros_state(initialized=True, error=None, subscriptions=subscriptions)
            last_discovery = 0.0
            while rclpy.ok() and not self.stop_event.is_set():
                rclpy.spin_once(self.node, timeout_sec=0.1)
                now = time.monotonic()
                if now - last_discovery >= float(self.config.get("ros", {}).get("discovery_refresh_seconds", 2.0)):
                    topics = [{"name": name, "types": types} for name, types in self.node.get_topic_names_and_types()]
                    self.store.set_ros_state(topics=topics, last_discovery=time.time())
                    last_discovery = now
        except Exception as exc:
            self.store.set_ros_state(initialized=False, error=f"{type(exc).__name__}: {exc}")
        finally:
            try:
                import rclpy
                if self.node is not None:
                    self.node.destroy_node()
                if rclpy.ok():
                    rclpy.shutdown()
            except Exception:
                pass

    def _worker(self) -> None:
        rgb_seen = tactile_seen = pose_seen = 0
        tactile_period = 1.0 / max(1.0, float(self.config.get("tactile", {}).get("max_fps", 30)))
        pose_period = 1.0 / max(1.0, float(self.config.get("hand", {}).get("max_fps", 60)))
        next_tactile = next_pose = 0.0
        while not self.stop_event.is_set():
            rgb_revision, rgb, hand_revision, hand = self.inputs.snapshot()
            if rgb is not None and rgb_revision != rgb_seen:
                rgb_seen = rgb_revision
                try:
                    payload = self.image.process_compressed(rgb) if rgb["kind"] == "compressed" else self.image.process_raw(rgb)
                    payload.update(topic=self.config["topics"]["rgb"]["name"], message_type=self.config["topics"]["rgb"]["type"])
                    self.store.update("rgb", payload, rgb.get("source_timestamp"))
                except Exception as exc:
                    self.store.set_ros_state(error=f"RGB processing: {type(exc).__name__}: {exc}")
            now = time.monotonic()
            emit_tactile = hand is not None and hand_revision != tactile_seen and now >= next_tactile
            emit_pose = hand is not None and hand_revision != pose_seen and now >= next_pose
            if emit_tactile:
                tactile_seen = hand_revision
                next_tactile = now + tactile_period
                for side in ("left", "right"):
                    try:
                        tactile = self.tactile[side].process(
                            hand[f"pressure_{side}"], hand.get(f"solve_state_{side}")
                        )
                        tactile.update(topic=self.config["topics"]["hand"]["name"], field=f"pressure_{side}")
                        self.store.update(f"tactile_{side}", tactile, hand.get(f"pressure_stamp_{side}"))
                    except Exception as exc:
                        self.store.set_ros_state(error=f"Tactile processing ({side}): {type(exc).__name__}: {exc}")
            if emit_pose:
                pose_seen = hand_revision
                next_pose = now + pose_period
                for side in ("left", "right"):
                    try:
                        pose = self.hand_pose.process(hand[f"solve_state_{side}"], side)
                        pose.update(topic=self.config["topics"]["hand"]["name"], field=f"solve_state_{side}", message_type=self.config["topics"]["hand"]["type"])
                        self.store.update(f"hand_pose_{side}", pose, hand.get(f"imu_stamp_{side}"))
                    except Exception as exc:
                        self.store.set_ros_state(error=f"Hand pose processing ({side}): {type(exc).__name__}: {exc}")
            time.sleep(0.001)

    def stop(self) -> None:
        self.stop_event.set()
        if self.ros_thread:
            self.ros_thread.join(timeout=3.0)
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
