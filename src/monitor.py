import asyncio
from typing import Optional
from .config import Config
from .utils.logger import info, error, success
from .clients.poller import TradePoller

class TradeMonitor:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.poller = TradePoller(queue)

    async def start(self):
        """Starts the polling monitor"""
        success(f"Starting Trade Monitor (Polling) for {Config.TRADER_ADDRESS}...")
        await self.poller.start()

    async def stop(self):
        """Stops the polling monitor"""
        await self.poller.stop()
        info("Trade Monitor stopped.")
