"""68-cell tactile processing.

Mapping, baseline, EMA and range logic are adapted from
Ego-loong-postprocess/scripts/live_tactile_68_web.py. The reference reads USB
serial; this module applies the same verified ordering to HandFrame pressure
arrays and supports one independent filter per hand.
"""
from __future__ import annotations

import statistics
from typing import Any

from .tactile_bend_decoupler import TactileBendDecoupler

SENSOR_NAMES = tuple(
    [f"A{i}" for i in range(4)]
    + [f"B{i}" for i in range(4)]
    + [f"C{i}" for i in range(4)]
    + [f"D{i}" for i in range(4)]
    + [f"E{i}" for i in range(4)]
    + [f"F{i}" for i in range(48)]
)

FINGER_POINTS = {
    "A": ((0.876, 0.518), (0.909, 0.502), (0.815, 0.607), (0.850, 0.586)),
    "B": ((0.614, 0.183), (0.643, 0.183), (0.599, 0.344), (0.632, 0.344)),
    "C": ((0.453, 0.115), (0.482, 0.115), (0.453, 0.288), (0.482, 0.288)),
    "D": ((0.294, 0.176), (0.323, 0.176), (0.309, 0.344), (0.342, 0.344)),
    "E": ((0.155, 0.318), (0.184, 0.318), (0.198, 0.483), (0.231, 0.483)),
}
PALM_ROWS = (
    (0.663, 0.247, 0.637), (0.702, 0.238, 0.663),
    (0.740, 0.231, 0.692), (0.778, 0.243, 0.677),
    (0.817, 0.265, 0.625), (0.855, 0.289, 0.570),
)


def build_points() -> list[list[float]]:
    points: list[list[float]] = []
    for key in "ABCDE":
        points.extend([[float(x), float(y)] for x, y in FINGER_POINTS[key]])
    for y, x0, x1 in PALM_ROWS:
        for col in range(8):
            points.append([x1 - (x1 - x0) * col / 7.0, y])
    if len(points) != 68:
        raise RuntimeError(f"Expected 68 tactile points, got {len(points)}")
    return points


POINTS = build_points()


class TactileProcessor:
    def __init__(self, config: dict[str, Any], side: str, *, allow_bend_decoupling: bool = True) -> None:
        self.side = side
        self.baseline_frames = max(1, int(config.get("baseline_frames", 24)))
        self.noise_gate = float(config.get("noise_gate", 1.5))
        self.ema_rise = float(config.get("ema_rise", 0.45))
        self.ema_fall = float(config.get("ema_fall", 0.22))
        self.auto_range = bool(config.get("auto_range", True))
        self.fixed_min = float(config.get("fixed_min", 0.0))
        self.fixed_max = max(self.fixed_min + 1.0, float(config.get("fixed_max", 160.0)))
        self.contact_threshold = float(config.get("contact_threshold", 4.0))
        self.display_deadzone = max(0.0, float(config.get("display_deadzone", self.contact_threshold)))
        self.high_threshold = float(config.get("high_threshold", 20.0))
        self.mirror = bool(config.get(f"mirror_{side}", False))
        bend_config = config if allow_bend_decoupling else {**config, "bend_decoupling": {"enabled": False}}
        self.bend_decoupler = TactileBendDecoupler(bend_config, side)
        self.reset()

    def reset(self) -> None:
        self._baseline_buffer: list[list[float]] = []
        self._baseline: list[float] | None = None
        self._filtered = [0.0] * 68
        self._display_range = self.fixed_max

    def set_auto_range(self, enabled: bool) -> None:
        self.auto_range = bool(enabled)

    def set_fixed_range(self, minimum: float, maximum: float) -> None:
        self.fixed_min = float(minimum)
        self.fixed_max = max(self.fixed_min + 1.0, float(maximum))
        self._display_range = self.fixed_max

    def process(
        self,
        values: list[float] | tuple[float, ...],
        solve_state: list[float] | tuple[float, ...] | None = None,
    ) -> dict[str, Any]:
        raw = [float(v) for v in values]
        if len(raw) != 68:
            raise ValueError(f"{self.side} tactile array must contain 68 values, got {len(raw)}")
        compensated, bend = self.bend_decoupler.apply(raw, solve_state)

        if self._baseline is None:
            self._baseline_buffer.append(compensated)
            if len(self._baseline_buffer) >= self.baseline_frames:
                self._baseline = [float(statistics.median(column)) for column in zip(*self._baseline_buffer)]
            delta = [0.0] * 68
        else:
            delta = []
            for index, value in enumerate(compensated):
                signed_delta = value - self._baseline[index]
                current = max(0.0, signed_delta)
                if current <= self.noise_gate:
                    current = 0.0
                    self._baseline[index] = self._baseline[index] * 0.999 + value * 0.001
                alpha = self.ema_rise if current >= self._filtered[index] else self.ema_fall
                self._filtered[index] = self._filtered[index] * (1.0 - alpha) + current * alpha
                if self._filtered[index] < max(0.25, self.noise_gate * 0.35):
                    self._filtered[index] = 0.0
                delta.append(self._filtered[index])

        peak = max(delta, default=0.0)
        if self.auto_range:
            target = max(4.0, peak * 1.2)
            self._display_range = target if target > self._display_range else self._display_range * 0.96 + target * 0.04
            self._display_range = max(8.0, min(4096.0, self._display_range))
        else:
            self._display_range = self.fixed_max
        # Filtering retains small residuals for diagnostics, but the artwork
        # should stay visually quiet until a value represents real contact.
        # Subtracting the deadzone also avoids auto-range magnifying an idle
        # residual into a prominent dot.
        display_min = max(self.fixed_min, self.display_deadzone)
        span = max(1e-6, self._display_range - display_min)
        display = [max(0.0, min(100.0, (value - display_min) / span * 100.0)) for value in delta]
        peak_index = delta.index(peak) if peak > 0 else -1
        return {
            "side": self.side,
            "raw": [round(v, 4) for v in raw],
            "compensated": [round(v, 4) for v in compensated],
            "smoothed": [round(v, 4) for v in delta],
            "display": [round(v, 3) for v in display],
            "baseline_ready": self._baseline is not None,
            "baseline_count": min(len(self._baseline_buffer), self.baseline_frames),
            "range_mode": "auto" if self.auto_range else "fixed",
            "display_min": self.fixed_min,
            "display_max": round(self._display_range, 3),
            "display_deadzone": self.display_deadzone,
            "maximum": round(peak, 4),
            "average": round(sum(delta) / 68.0, 4),
            "nonzero_count": sum(value > 0 for value in delta),
            "contact_count": sum(value >= self.contact_threshold for value in delta),
            "high_count": sum(value >= self.high_threshold for value in delta),
            "peak_sensor": SENSOR_NAMES[peak_index] if peak_index >= 0 else None,
            "bend_decoupling": bend,
            "mirror": self.mirror,
            "unit": "raw/Delta (physical unit pending confirmation)",
        }


def layout_payload() -> dict[str, Any]:
    return {
        "names": list(SENSOR_NAMES),
        "points": POINTS,
        "groups": {
            "thumb": [0, 3], "index": [4, 7], "middle": [8, 11],
            "ring": [12, 15], "little": [16, 19], "palm": [20, 67],
        },
        "source": "/home/lenovo/Ego-loong-postprocess/scripts/live_tactile_68_web.py",
        "mirror_note": "Reference is single-hand only; per-side mirroring is configurable and pending hardware confirmation.",
    }
