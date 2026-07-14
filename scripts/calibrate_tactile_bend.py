#!/usr/bin/env python3
"""Record a no-contact hand sweep from HandFrame and build a pose atlas."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.tactile_bend_decoupler import FLEX_STATE_INDICES  # noqa: E402


FINGER_NAMES = np.array(("thumb", "index", "middle", "ring", "little"), dtype=object)


def extract_sample(message: Any, side: str) -> tuple[np.ndarray, np.ndarray]:
    pressure = np.asarray(getattr(message, f"pressure_{side}"), dtype=np.float64).reshape(-1)
    state = np.asarray(getattr(message, f"solve_state_{side}"), dtype=np.float64).reshape(-1)
    if pressure.size != 68 or state.size != 27:
        raise ValueError(f"expected pressure[68]/solve_state[27], got {pressure.size}/{state.size}")
    pose = state[list(FLEX_STATE_INDICES)]
    if not np.all(np.isfinite(pressure)) or not np.all(np.isfinite(pose)):
        raise ValueError("sample contains NaN or infinity")
    if np.any(np.abs(pose) >= 1.0e8):
        raise ValueError("solve_state is not ready")
    return pressure, pose


def save_calibration(
    path: Path,
    side: str,
    pressures: np.ndarray,
    poses: np.ndarray,
    *,
    max_templates: int = 0,
) -> int:
    if pressures.ndim != 2 or pressures.shape[1] != 68:
        raise ValueError(f"pressures must have shape (N,68), got {pressures.shape}")
    if poses.shape != (pressures.shape[0], 14):
        raise ValueError(f"poses must have shape ({pressures.shape[0]},14), got {poses.shape}")
    if pressures.shape[0] < 20:
        raise ValueError(f"at least 20 valid frames are required, got {pressures.shape[0]}")
    if max_templates > 0 and pressures.shape[0] > max_templates:
        indices = np.linspace(0, pressures.shape[0] - 1, max_templates, dtype=np.int64)
        pressures = pressures[indices]
        poses = poses[indices]

    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        calib_version=np.int32(5),
        sensor_type=np.int32(1 if side == "left" else 2),
        finger_names=FINGER_NAMES,
        pose_mode=np.array("joint"),
        bend_center=np.median(poses, axis=0),
        bend_scale=np.maximum(np.std(poses, axis=0), 1.0),
        atlas_bends=poses,
        atlas_fingers=pressures[:, :20].reshape(-1, 5, 2, 2),
        atlas_palm=pressures[:, 20:],
        atlas_mode=np.array("nn"),
        knn_sigma=np.float64(0.0),
        knn_k=np.int32(0),
    )
    return int(pressures.shape[0])


def record(args: argparse.Namespace) -> None:
    os.environ["ROS_DOMAIN_ID"] = str(args.domain_id)
    os.environ.setdefault("RMW_IMPLEMENTATION", "rmw_zenoh_cpp")
    if not os.environ.get("ZENOH_SESSION_CONFIG_URI") and not os.environ.get("ZENOH_CONFIG_OVERRIDE"):
        endpoint = os.environ.get("EGO_ZENOH_ROUTER_ENDPOINT", "tcp/192.168.3.13:7447")
        os.environ["ZENOH_CONFIG_OVERRIDE"] = f'mode="client";connect/endpoints=["{endpoint}"]'
    import rclpy
    from hand_frame.msg import HandFrame
    from rclpy.node import Node
    from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

    pressures: list[np.ndarray] = []
    poses: list[np.ndarray] = []
    rejected = 0

    class CalibrationNode(Node):
        def __init__(self) -> None:
            super().__init__("ego_loong_tactile_bend_calibration")
            qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE,
                             history=HistoryPolicy.KEEP_LAST)
            self.create_subscription(HandFrame, args.topic, self.on_frame, qos)

        def on_frame(self, message: HandFrame) -> None:
            nonlocal rejected
            try:
                pressure, pose = extract_sample(message, args.side)
            except ValueError:
                rejected += 1
                return
            pressures.append(pressure)
            poses.append(pose)

    if not args.yes:
        print(f"{args.side} 手弯曲解耦标定：全程不要接触物体，缓慢握拳再伸直，持续 {args.duration:.1f} 秒。")
        input("准备好后按 Enter 开始…")

    rclpy.init(args=None)
    node = CalibrationNode()
    started = time.monotonic()
    try:
        while rclpy.ok() and time.monotonic() - started < args.duration:
            rclpy.spin_once(node, timeout_sec=0.1)
            elapsed = time.monotonic() - started
            print(f"\r采集中 {elapsed:5.1f}/{args.duration:.1f}s  有效帧 {len(pressures)}", end="", flush=True)
    finally:
        node.destroy_node()
        rclpy.shutdown()
        print()

    if not pressures:
        raise SystemExit(f"未收到有效 {args.topic} 数据；被拒绝帧数 {rejected}")
    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    count = save_calibration(
        output.resolve(), args.side, np.stack(pressures), np.stack(poses),
        max_templates=args.max_templates,
    )
    print(f"标定完成：{count} 个模板 -> {output.resolve()}")
    print(f"配置项：calibration_{args.side}: {output.resolve().relative_to(PROJECT_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="从 /hand_frame 采集空手慢握拳姿态库")
    parser.add_argument("--side", choices=("left", "right"), required=True)
    parser.add_argument("--topic", default="/hand_frame")
    parser.add_argument("--duration", type=float, default=12.0)
    parser.add_argument("--domain-id", type=int, default=int(os.environ.get("ROS_DOMAIN_ID", "0")))
    parser.add_argument("--output", default=None)
    parser.add_argument("--max-templates", type=int, default=0, help="0 表示保留全部有效帧")
    parser.add_argument("--yes", action="store_true", help="跳过开始前确认")
    args = parser.parse_args()
    if args.output is None:
        args.output = f"config/tactile/joint_decouple_calib_{args.side}.npz"
    if args.duration <= 0:
        parser.error("--duration must be positive")
    record(args)


if __name__ == "__main__":
    main()
