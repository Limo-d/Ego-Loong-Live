"""Thread-safe latest-frame store; no unbounded message queues."""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RateCounter:
    times: deque[float] = field(default_factory=lambda: deque(maxlen=256))
    count: int = 0
    last_wall: float | None = None
    last_source: float | None = None
    timeouts: int = 0
    was_timed_out: bool = False

    def mark(self, now: float, source_timestamp: float | None) -> None:
        self.count += 1
        self.last_wall = now
        self.last_source = source_timestamp
        self.times.append(now)
        self.was_timed_out = False

    def hz(self) -> float:
        if len(self.times) < 2:
            return 0.0
        span = self.times[-1] - self.times[0]
        return (len(self.times) - 1) / span if span > 0 else 0.0


class DataStore:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.lock = threading.RLock()
        self.started_wall = time.time()
        self.started_mono = time.monotonic()
        self.channels: dict[str, dict[str, Any]] = {}
        self.rates: dict[str, RateCounter] = {}
        self.ros_state: dict[str, Any] = {
            "initialized": False,
            "error": None,
            "topics": [],
            "subscriptions": [],
            "last_discovery": None,
        }
        self.mode = "mock" if config.get("mode", {}).get("mock") else "ros"

    def update(self, channel: str, data: dict[str, Any], source_timestamp: float | None = None) -> int:
        now_wall = time.time()
        now_mono = time.monotonic()
        with self.lock:
            old = self.channels.get(channel)
            revision = int(old.get("revision", 0) if old else 0) + 1
            rate = self.rates.setdefault(channel, RateCounter())
            rate.mark(now_mono, source_timestamp)
            payload = dict(data)
            raw_latency_ms = None if not source_timestamp else (now_wall - source_timestamp) * 1000.0
            # Recorded bags retain historical header stamps. Flag a large wall-clock
            # difference instead of reporting it as live network latency.
            clock_mismatch = raw_latency_ms is not None and abs(raw_latency_ms) > 60_000.0
            payload.update({
                "received_at": now_wall,
                "source_timestamp": source_timestamp,
                "latency_ms": None if clock_mismatch else (None if raw_latency_ms is None else max(0.0, raw_latency_ms)),
                "clock_mismatch": clock_mismatch,
                "frame_count": rate.count,
                "hz": round(rate.hz(), 2),
            })
            self.channels[channel] = {
                "revision": revision,
                "updated_mono": now_mono,
                "data": payload,
            }
            return revision

    def channel(self, name: str) -> dict[str, Any] | None:
        with self.lock:
            item = self.channels.get(name)
            if item is None:
                return None
            return {"revision": item["revision"], "data": dict(item["data"])}

    def updates_since(self, revisions: dict[str, int]) -> list[tuple[str, int, dict[str, Any]]]:
        out = []
        with self.lock:
            for name, item in self.channels.items():
                if item["revision"] > revisions.get(name, 0):
                    out.append((name, item["revision"], dict(item["data"])))
        return out

    def set_ros_state(self, **values: Any) -> None:
        with self.lock:
            self.ros_state.update(values)

    def _timeout_for(self, channel: str) -> float:
        timeouts = self.config.get("timeout", {})
        if channel == "rgb":
            return float(timeouts.get("rgb_seconds", 2.0))
        if channel.startswith("tactile"):
            return float(timeouts.get("tactile_seconds", 1.0))
        return float(timeouts.get("hand_seconds", 1.0))

    def status(self, websocket_clients: int = 0, process: dict[str, Any] | None = None) -> dict[str, Any]:
        now_mono = time.monotonic()
        now_wall = time.time()
        with self.lock:
            channel_status: dict[str, Any] = {}
            for name in ("rgb", "tactile_left", "tactile_right", "hand_pose_left", "hand_pose_right"):
                item = self.channels.get(name)
                rate = self.rates.setdefault(name, RateCounter())
                age = None if item is None else now_mono - item["updated_mono"]
                timed_out = item is None or age > self._timeout_for(name)
                if item is not None and timed_out and not rate.was_timed_out:
                    rate.timeouts += 1
                    rate.was_timed_out = True
                channel_status[name] = {
                    "connected": item is not None and not timed_out,
                    "timed_out": timed_out,
                    "age_seconds": None if age is None else round(age, 3),
                    "hz": round(rate.hz(), 2),
                    "frame_count": rate.count,
                    "timeout_count": rate.timeouts,
                    "last_message": None if item is None else item["data"].get("received_at"),
                    "latency_ms": None if item is None else item["data"].get("latency_ms"),
                }
            return {
                "type": "system_status",
                "timestamp": now_wall,
                "mode": self.mode,
                "uptime_seconds": round(now_mono - self.started_mono, 1),
                "ros": dict(self.ros_state),
                "channels": channel_status,
                "websocket_clients": websocket_clients,
                "process": process or {},
            }

