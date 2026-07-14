"""Safe acquisition metadata and deliberately disconnected control placeholders."""
from __future__ import annotations

import threading
import time
from typing import Any


class AcquisitionManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.lock = threading.RLock()
        self.data = {
            "collecting": False,
            "state": "preview",
            "operator": config.get("operator", ""),
            "task_name": config.get("task_name", ""),
            "scene_name": config.get("scene_name", ""),
            "save_path": config.get("save_path", ""),
            "started_at": None,
            "event_markers": 0,
            "control_connected": False,
            "message": "真实采集控制接口暂未接入；按钮不会执行系统命令或操作 ROS 进程。",
        }

    def snapshot(self, counters: dict[str, int] | None = None) -> dict[str, Any]:
        with self.lock:
            result = dict(self.data)
        result["duration_seconds"] = 0.0 if not result["started_at"] else max(0.0, time.time() - result["started_at"])
        result["counters"] = counters or {}
        return result

    def update_metadata(self, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {"operator", "task_name", "scene_name", "save_path"}
        with self.lock:
            for key in allowed:
                if key in values:
                    self.data[key] = str(values[key])
            return dict(self.data)

    def unsupported_control(self, action: str) -> dict[str, Any]:
        return {
            "ok": False,
            "action": action,
            "implemented": False,
            "message": "真实采集控制接口暂未接入；未执行任何外部命令。",
        }

