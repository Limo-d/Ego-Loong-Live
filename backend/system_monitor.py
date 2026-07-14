"""Small psutil-based process monitor."""
from __future__ import annotations

import os
import time

import psutil


class SystemMonitor:
    def __init__(self) -> None:
        self.process = psutil.Process(os.getpid())
        self.process.cpu_percent(None)
        self.last_net = psutil.net_io_counters()
        self.last_time = time.monotonic()

    def snapshot(self) -> dict:
        now = time.monotonic()
        net = psutil.net_io_counters()
        dt = max(1e-6, now - self.last_time)
        sent_rate = (net.bytes_sent - self.last_net.bytes_sent) / dt
        received_rate = (net.bytes_recv - self.last_net.bytes_recv) / dt
        self.last_net, self.last_time = net, now
        memory = self.process.memory_info()
        return {
            "pid": self.process.pid,
            "cpu_percent": round(self.process.cpu_percent(None), 2),
            "memory_rss_mb": round(memory.rss / (1024 * 1024), 2),
            "system_memory_percent": round(psutil.virtual_memory().percent, 2),
            "network_tx_kbps": round(sent_rate / 1024, 2),
            "network_rx_kbps": round(received_rate / 1024, 2),
        }

