"""FastAPI application entry point for Ego-Loong Live."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .acquisition_manager import AcquisitionManager
from .config import PROJECT_ROOT, load_config, public_config
from .data_store import DataStore
from .mock_data import MockDataEngine
from .ros_node import RosBridge
from .system_monitor import SystemMonitor
from .tactile_processor import layout_payload
from .websocket_manager import Client, WebSocketManager

FRONTEND = PROJECT_ROOT / "frontend"


class Runtime:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.store = DataStore(config)
        self.websocket = WebSocketManager(queue_size=16)
        self.acquisition = AcquisitionManager(config.get("acquisition", {}))
        self.monitor = SystemMonitor()
        self.source: MockDataEngine | RosBridge | None = None
        self.tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        self.source = MockDataEngine(self.config, self.store) if self.config.get("mode", {}).get("mock") else RosBridge(self.config, self.store)
        self.source.start()
        self.tasks = [asyncio.create_task(self._broadcast_channels()), asyncio.create_task(self._broadcast_status())]

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if self.source:
            self.source.stop()
        await self.websocket.close_all()

    def counters(self) -> dict[str, int]:
        result = {}
        for channel, label in (("rgb", "rgb_frames"), ("hand_pose_left", "hand_msg_frames"), ("tactile_left", "tactile_left_frames"), ("tactile_right", "tactile_right_frames")):
            rate = self.store.rates.get(channel)
            result[label] = 0 if rate is None else rate.count
        return result

    async def _broadcast_channels(self) -> None:
        revisions: dict[str, int] = {}
        while True:
            for channel, revision, data in self.store.updates_since(revisions):
                revisions[channel] = revision
                await self.websocket.broadcast({"type": channel, "timestamp": data.get("received_at"), "data": data})
            await asyncio.sleep(1.0 / 120.0)

    async def _broadcast_status(self) -> None:
        while True:
            status = self.store.status(self.websocket.count, self.monitor.snapshot())
            await self.websocket.broadcast(status)
            await self.websocket.broadcast({"type": "acquisition_status", "timestamp": status["timestamp"], "data": self.acquisition.snapshot(self.counters())})
            await asyncio.sleep(1.0)


def create_app(config: dict[str, Any] | None = None) -> FastAPI:
    cfg = config or load_config()
    runtime = Runtime(cfg)

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        await runtime.start()
        yield
        await runtime.stop()

    app = FastAPI(title="Ego-Loong Live", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(FRONTEND / "index.html")

    @app.get("/dashboard", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(FRONTEND / "dashboard.html")

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "mode": runtime.store.mode, "version": "0.1.0"}

    @app.get("/api/config")
    async def api_config() -> dict[str, Any]:
        return public_config(cfg)

    @app.get("/api/tactile/layout")
    async def tactile_layout() -> dict[str, Any]:
        return layout_payload()

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        return runtime.store.status(runtime.websocket.count, runtime.monitor.snapshot())

    @app.get("/api/acquisition")
    async def acquisition() -> dict[str, Any]:
        return runtime.acquisition.snapshot(runtime.counters())

    @app.post("/api/acquisition/metadata")
    async def acquisition_metadata(values: dict[str, Any]) -> dict[str, Any]:
        return runtime.acquisition.update_metadata(values)

    @app.post("/api/acquisition/control/{action}")
    async def acquisition_control(action: str) -> dict[str, Any]:
        if action not in {"new", "start", "pause", "resume", "stop", "mark"}:
            raise HTTPException(status_code=404, detail="unknown acquisition action")
        result = runtime.acquisition.unsupported_control(action)
        raise HTTPException(status_code=501, detail=result)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        client: Client = await runtime.websocket.connect(websocket)
        try:
            await runtime.websocket.send(client, runtime.store.status(runtime.websocket.count, runtime.monitor.snapshot()))
            await runtime.websocket.send(client, {"type": "acquisition_status", "data": runtime.acquisition.snapshot(runtime.counters())})
            # A newly opened page must receive the latest retained frame even
            # when the ROS Topic has already timed out. This keeps the last
            # real tactile/FK state visible while timeout remains explicit.
            for channel in ("rgb", "tactile_left", "tactile_right", "hand_pose_left", "hand_pose_right"):
                item = runtime.store.channel(channel)
                if item is not None:
                    await runtime.websocket.send(
                        client,
                        {"type": channel, "timestamp": item["data"].get("received_at"), "data": item["data"]},
                    )
            while True:
                message = await websocket.receive_text()
                if message == "ping":
                    await runtime.websocket.send(client, {"type": "pong"})
        except WebSocketDisconnect:
            pass
        finally:
            await runtime.websocket.disconnect(client)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Ego-Loong Live real-time visualization server")
    parser.add_argument("--config", default=None)
    parser.add_argument("--mock", action="store_true", help="force deterministic mock mode")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    config = load_config(args.config, mock_override=True if args.mock else None)
    host = args.host or config.get("server", {}).get("host", "0.0.0.0")
    port = args.port or int(config.get("server", {}).get("port", 8000))
    mode = "MOCK" if config.get("mode", {}).get("mock") else "ROS"
    print("Ego-Loong Live started")
    print(f"Mode: {mode}")
    print(f"Web UI: http://localhost:{port}")
    print(f"WebSocket: ws://localhost:{port}/ws")
    print(f"ROS_DOMAIN_ID: {config.get('ros', {}).get('domain_id', 0)}")
    print(f"RGB topic: {config['topics']['rgb']['name']} [{config['topics']['rgb']['type']}]")
    print(f"Hand topic: {config['topics']['hand']['name']} [{config['topics']['hand']['type']}]")
    print(f"Config: {config['_config_path']}")
    uvicorn.run(create_app(config), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
