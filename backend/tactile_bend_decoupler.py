"""Pose-atlas compensation for bend-induced tactile signals.

The calibration format is compatible with curved_decouple_simple.py v4/v5:
each atlas row contains a 14-DoF no-contact hand pose and its corresponding
68-channel tactile template. Runtime compensation selects the nearest pose in
normalized joint space and subtracts that template before zero calibration.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


FLEX_STATE_INDICES = (16, 18, 0, 2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15)
EXPECTED_SENSOR_TYPE = {"left": 1, "right": 2}


class TactileBendDecoupler:
    def __init__(self, config: dict[str, Any], side: str) -> None:
        options = config.get("bend_decoupling", {})
        self.side = side
        self.requested = bool(options.get("enabled", False))
        self.max_pose_distance = max(0.0, float(options.get("max_pose_distance", 6.0)))
        self.path: Path | None = None
        self.error: str | None = None
        self.atlas_poses: np.ndarray | None = None
        self.atlas_normalized: np.ndarray | None = None
        self.atlas_tactile: np.ndarray | None = None
        self.pose_center: np.ndarray | None = None
        self.pose_scale: np.ndarray | None = None

        configured = str(options.get(f"calibration_{side}", "")).strip()
        if not self.requested or not configured:
            return
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        self.path = path.resolve()
        try:
            self._load(self.path)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"

    @property
    def ready(self) -> bool:
        return self.atlas_normalized is not None and self.atlas_tactile is not None

    def _load(self, path: Path) -> None:
        with np.load(path, allow_pickle=True) as data:
            version = int(data["calib_version"])
            if version not in (4, 5):
                raise ValueError(f"unsupported calibration version {version}")
            sensor_type = int(data["sensor_type"])
            if sensor_type != EXPECTED_SENSOR_TYPE[self.side]:
                raise ValueError(
                    f"calibration sensor_type={sensor_type} does not match {self.side} hand"
                )
            pose_mode = str(np.asarray(data["pose_mode"]).item())
            if pose_mode != "joint":
                raise ValueError(f"pose_mode must be 'joint', got {pose_mode!r}")
            poses = np.asarray(data["atlas_bends"], dtype=np.float64)
            fingers = np.asarray(data["atlas_fingers"], dtype=np.float64)
            palm = np.asarray(data["atlas_palm"], dtype=np.float64)
            center = np.asarray(data["bend_center"], dtype=np.float64)
            scale = np.maximum(np.asarray(data["bend_scale"], dtype=np.float64), 1e-6)

        if poses.ndim != 2 or poses.shape[1] != len(FLEX_STATE_INDICES):
            raise ValueError(f"atlas_bends must have shape (N, 14), got {poses.shape}")
        count = poses.shape[0]
        if fingers.shape != (count, 5, 2, 2) or palm.shape != (count, 48):
            raise ValueError(
                f"tactile atlas shapes must be (N,5,2,2)/(N,48), got {fingers.shape}/{palm.shape}"
            )
        if center.shape != (14,) or scale.shape != (14,):
            raise ValueError("bend_center and bend_scale must contain 14 values")

        self.atlas_poses = poses
        self.pose_center = center
        self.pose_scale = scale
        self.atlas_normalized = (poses - center) / scale
        self.atlas_tactile = np.concatenate((fingers.reshape(count, 20), palm), axis=1)

    def apply(
        self,
        values: list[float],
        solve_state: list[float] | tuple[float, ...] | None,
    ) -> tuple[list[float], dict[str, Any]]:
        metadata: dict[str, Any] = {
            "requested": self.requested,
            "ready": self.ready,
            "applied": False,
            "calibration": self.path.name if self.path else None,
            "error": self.error,
            "pose_distance": None,
            "template_index": None,
        }
        if not self.ready or solve_state is None:
            return values.copy(), metadata

        state = np.asarray(solve_state, dtype=np.float64).reshape(-1)
        if state.size != 27:
            metadata["error"] = f"solve_state must contain 27 values, got {state.size}"
            return values.copy(), metadata
        pose = state[list(FLEX_STATE_INDICES)]
        if not np.all(np.isfinite(pose)) or np.any(np.abs(pose) >= 1.0e8):
            metadata["error"] = "solve_state flexion values are not valid"
            return values.copy(), metadata

        assert self.pose_center is not None
        assert self.pose_scale is not None
        assert self.atlas_normalized is not None
        assert self.atlas_tactile is not None
        query = (pose - self.pose_center) / self.pose_scale
        distance2 = np.sum((self.atlas_normalized - query) ** 2, axis=1)
        index = int(np.argmin(distance2))
        distance = float(np.sqrt(distance2[index]))
        metadata["pose_distance"] = round(distance, 4)
        metadata["template_index"] = index
        if self.max_pose_distance > 0 and distance > self.max_pose_distance:
            metadata["error"] = (
                f"nearest calibration pose distance {distance:.3f} exceeds "
                f"limit {self.max_pose_distance:.3f}"
            )
            return values.copy(), metadata

        compensated = np.asarray(values, dtype=np.float64) - self.atlas_tactile[index]
        metadata["applied"] = True
        metadata["error"] = None
        return compensated.tolist(), metadata
