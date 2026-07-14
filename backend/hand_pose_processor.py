"""Verified state27 parsing and human-hand forward kinematics.

This is a dependency-light port of Retarget/retarget/hand_retarget/layout.py and
human_fk.py. It preserves their index order, signs, coordinate system and bone
geometry, replacing SciPy Rotation with equivalent NumPy matrices.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .models import ANGLE_LAYOUT, BONE_EDGES, FINGERS, JOINT_NAMES, SENTINEL_ABS


def _axis_angle(axis: tuple[float, float, float], degrees: float) -> np.ndarray:
    vector = np.asarray(axis, dtype=np.float64)
    vector /= max(np.linalg.norm(vector), 1e-12)
    x, y, z = vector
    angle = math.radians(float(degrees))
    c, s, one = math.cos(angle), math.sin(angle), 1.0 - math.cos(angle)
    return np.array([
        [c + x*x*one, x*y*one - z*s, x*z*one + y*s],
        [y*x*one + z*s, c + y*y*one, y*z*one - x*s],
        [z*x*one - y*s, z*y*one + x*s, c + z*z*one],
    ], dtype=np.float64)


def _quat_wxyz_matrix(quaternion: np.ndarray) -> np.ndarray:
    q = np.asarray(quaternion, dtype=np.float64)
    q /= max(np.linalg.norm(q), 1e-12)
    w, x, y, z = q
    return np.array([
        [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
        [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)],
    ], dtype=np.float64)


class HandPoseProcessor:
    def __init__(self, config: dict[str, Any]) -> None:
        geometry_path = Path(config["geometry_config"]).expanduser().resolve()
        self.geometry_path = geometry_path
        self.geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
        self.sentinel_abs = float(config.get("sentinel_abs", SENTINEL_ABS))
        self.apply_palm_orientation = bool(config.get("apply_palm_orientation", True))
        self.anchor_initial_palm = bool(config.get("anchor_initial_palm", True))
        self.freeze_palm_orientation = bool(config.get("freeze_palm_orientation", False))
        self._palm_references: dict[str, np.ndarray] = {}
        viz = self.geometry.get("viz", {})
        self.flex_sign = int(viz.get("flex_sign", 1))
        self.swing_sign = int(viz.get("swing_sign", 1))
        # origin/handviz.js treats palm_mount_corr_deg as one rotation vector:
        # its direction is the axis and its Euclidean norm is the angle.  It is
        # applied at every finger-chain root without moving that root.
        palm_corr = np.asarray(viz.get("palm_mount_corr_deg", [0.0, 0.0, 0.0]), dtype=np.float64)
        palm_corr_angle = float(np.linalg.norm(palm_corr))
        self.palm_mount_correction = (
            _axis_angle(tuple(palm_corr / palm_corr_angle), palm_corr_angle)
            if palm_corr_angle > 1e-6 else np.eye(3, dtype=np.float64)
        )
        self.bones_mm = {name: np.asarray(value, dtype=np.float64) for name, value in self.geometry["bones_mm"].items()}
        self.offsets_mm = {name: np.asarray(value, dtype=np.float64) for name, value in self.geometry["mcp_offsets_mm"].items()}

    def _clean(self, state: np.ndarray, index: int) -> tuple[float, bool]:
        value = float(state[index])
        valid = math.isfinite(value) and abs(value) < self.sentinel_abs
        return (value if valid else 0.0), valid

    def process(self, values: list[float] | tuple[float, ...], side: str) -> dict[str, Any]:
        state = np.asarray(values, dtype=np.float64).reshape(-1)
        if state.size != 27:
            raise ValueError(f"state27 must have 27 numbers, got {state.size}")
        is_left = side == "left"
        present = bool(np.any(np.isfinite(state) & (np.abs(state) < self.sentinel_abs)))
        if not present:
            self._palm_references.pop(side, None)
        mirror = 1.0 if is_left else -1.0
        wrist = np.array([-14.0, 0.0, 0.0], dtype=np.float64)
        finger_points: dict[str, np.ndarray] = {}
        valid_fingers: dict[str, bool] = {}

        for finger_index, name in enumerate(("index", "middle", "ring", "little")):
            start = finger_index * 4
            angle_values = [self._clean(state, start + i) for i in range(4)]
            a = [item[0] for item in angle_values]
            valid_fingers[name] = any(item[1] for item in angle_values)
            joints = ((a[0], a[1]), (a[2], 0.0), (a[3], 0.0))
            offset = self.offsets_mm[name]
            point = np.array([offset[0], offset[1], mirror * offset[2]], dtype=np.float64)
            points = [point.copy()]
            cumulative = self.palm_mount_correction.copy()
            for segment, (flex, swing) in enumerate(joints):
                rotation = _axis_angle((0, 1, 0), mirror * self.swing_sign * swing) @ _axis_angle((0, 0, 1), -self.flex_sign * flex)
                cumulative = cumulative @ rotation
                point = point + cumulative @ np.array([self.bones_mm[name][segment], 0.0, 0.0])
                points.append(point.copy())
            finger_points[name] = np.asarray(points)

        thumb_angles = [self._clean(state, index) for index in (16, 17, 18)]
        cmc_values = np.asarray(state[19:23], dtype=np.float64)
        cmc_valid = bool(np.all(np.isfinite(cmc_values)) and np.all(np.abs(cmc_values) < self.sentinel_abs))
        cmc_values = cmc_values / max(np.linalg.norm(cmc_values), 1e-12) if cmc_valid else np.array([1.0, 0.0, 0.0, 0.0])
        transform = _axis_angle((1, 0, 0), -90.0)
        # Both solve_state streams already express CMC/MCP rotations in their
        # own calibrated hand frame. Use the same rotation rule for both; only
        # the configured root position is mirrored for the right hand.
        cumulative = self.palm_mount_correction @ transform @ _quat_wxyz_matrix(cmc_values) @ transform.T
        offset = self.offsets_mm["thumb"]
        point = np.array([offset[0], offset[1], mirror * offset[2]], dtype=np.float64)
        thumb_points = [point.copy()]
        point = point + cumulative @ np.array([self.bones_mm["thumb"][0], 0.0, 0.0]); thumb_points.append(point.copy())
        cumulative = cumulative @ (_axis_angle((0, 1, 0), thumb_angles[1][0]) @ _axis_angle((0, 0, 1), thumb_angles[0][0]))
        point = point + cumulative @ np.array([self.bones_mm["thumb"][1], 0.0, 0.0]); thumb_points.append(point.copy())
        cumulative = cumulative @ _axis_angle((0, 0, 1), thumb_angles[2][0])
        point = point + cumulative @ np.array([self.bones_mm["thumb"][2], 0.0, 0.0]); thumb_points.append(point.copy())
        finger_points["thumb"] = np.asarray(thumb_points)
        valid_fingers["thumb"] = cmc_valid or any(item[1] for item in thumb_angles)

        ordered = [wrist]
        for name in FINGERS:
            ordered.extend(finger_points[name])
        points = np.asarray(ordered, dtype=np.float64) * 1e-3
        palm = np.asarray(state[23:27], dtype=np.float64)
        palm_valid = bool(np.all(np.isfinite(palm)) and np.all(np.abs(palm) < self.sentinel_abs))
        if self.apply_palm_orientation and palm_valid and not self.freeze_palm_orientation:
            rotation = _quat_wxyz_matrix(palm)
            if self.anchor_initial_palm:
                reference = self._palm_references.get(side)
                if reference is None:
                    reference = rotation.copy()
                    self._palm_references[side] = reference
                rotation = rotation @ reference.T
            root = points[0].copy()
            points = root + (rotation @ (points - root).T).T

        angle_rows = []
        for index, (finger, joint) in enumerate(ANGLE_LAYOUT):
            value, valid = self._clean(state, index)
            angle_rows.append({"index": index, "finger": finger, "joint": joint, "name": f"{finger}.{joint}", "degrees": round(value, 4), "valid": valid})
        return {
            "side": side,
            "present": present,
            "coordinate_system": "Retarget human model: x=fingertip, y=dorsal, z=thumb-side; meters",
            "joint_names": list(JOINT_NAMES),
            "points": np.round(points, 6).tolist(),
            "bones": [list(edge) for edge in BONE_EDGES],
            "angles": angle_rows,
            "finger_valid": valid_fingers,
            "palm_quaternion_wxyz": np.round(palm, 7).tolist() if palm_valid else None,
            "palm_orientation_mode": (
                "fixed_canonical" if self.freeze_palm_orientation
                else "relative_to_first_valid" if self.anchor_initial_palm
                else "absolute"
            ),
            "thumb_cmc_quaternion_wxyz": np.round(cmc_values, 7).tolist() if cmc_valid else None,
            "source_geometry": str(self.geometry_path),
        }
