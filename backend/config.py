"""Configuration loading with environment overrides."""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "config.yaml"


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config(path: str | Path | None = None, mock_override: bool | None = None) -> dict[str, Any]:
    config_path = Path(path or os.environ.get("EGO_LOONG_LIVE_CONFIG", DEFAULT_CONFIG)).expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}
    config = copy.deepcopy(config)
    config["_config_path"] = str(config_path)
    config["_project_root"] = str(PROJECT_ROOT)

    if mock_override is not None:
        config.setdefault("mode", {})["mock"] = bool(mock_override)
    elif "EGO_LOONG_LIVE_MOCK" in os.environ:
        config.setdefault("mode", {})["mock"] = _as_bool(os.environ["EGO_LOONG_LIVE_MOCK"])

    if "EGO_LOONG_LIVE_PORT" in os.environ:
        config.setdefault("server", {})["port"] = int(os.environ["EGO_LOONG_LIVE_PORT"])
    if "EGO_LOONG_LIVE_HOST" in os.environ:
        config.setdefault("server", {})["host"] = os.environ["EGO_LOONG_LIVE_HOST"]

    geometry = Path(config.get("hand", {}).get("geometry_config", ""))
    if geometry and not geometry.is_absolute():
        geometry = PROJECT_ROOT / geometry
    config.setdefault("hand", {})["geometry_config"] = str(geometry.resolve())
    return config


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return the browser-safe portion of the YAML configuration."""
    keys = ("mode", "ros", "topics", "rgb", "hand", "tactile", "timeout", "acquisition")
    return {key: copy.deepcopy(config.get(key, {})) for key in keys}

