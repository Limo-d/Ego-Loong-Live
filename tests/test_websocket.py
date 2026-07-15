import asyncio
import json
import unittest

from backend.websocket_manager import WebSocketManager


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.messages = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, payload):
        self.messages.append(json.loads(payload))


class WebSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_send_disconnect(self):
        manager = WebSocketManager(queue_size=1)
        socket = FakeWebSocket()
        client = await manager.connect(socket)
        await manager.send(client, {"type": "system_status", "ok": True})
        await asyncio.sleep(.01)
        self.assertTrue(socket.accepted)
        self.assertEqual(socket.messages[-1]["type"], "system_status")
        await manager.disconnect(client)
        self.assertEqual(manager.count, 0)

    async def test_same_channel_keeps_only_latest(self):
        manager = WebSocketManager(queue_size=4)
        socket = FakeWebSocket()
        client = await manager.connect(socket)
        for frame in range(20):
            await manager.send(client, {"type": "rgb", "frame": frame})
        await asyncio.sleep(.01)
        self.assertEqual(len(socket.messages), 1)
        self.assertEqual(socket.messages[0]["frame"], 19)
        await manager.disconnect(client)


if __name__ == "__main__":
    unittest.main()
