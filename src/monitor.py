import asyncio
import json
import websockets
from typing import Optional, List
from .config import Config
from .utils.logger import info, error, success, warning, trade_detect
import ssl
import certifi

RTDS_URL = 'wss://ws-live-data.polymarket.com'

class TradeMonitor:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.is_running = False
        self.ws: Optional[websockets.client.WebSocketClientProtocol] = None
        self.reconnect_attempts = 0
        self.MAX_RECONNECT_ATTEMPTS = 10
        self.RECONNECT_DELAY = 5

    async def start(self):
        self.is_running = True
        success(f"Starting Trade Monitor for {Config.TRADER_ADDRESS}...")
        await self._reconnect_loop()

    async def stop(self):
        self.is_running = False
        if self.ws:
            await self.ws.close()
        info("Trade Monitor stopped.")

    async def _reconnect_loop(self):
        while self.is_running:
            try:
                await self._connect()
                # If connect returns, it means connection lost or closed
                if not self.is_running: break
                
                self.reconnect_attempts += 1
                delay = self.RECONNECT_DELAY * min(self.reconnect_attempts, 5)
                info(f"Reconnecting in {delay}s...")
                await asyncio.sleep(delay)
            except Exception as e:
                error(f"Reconnection error: {e}")
                self.reconnect_attempts += 1
                await asyncio.sleep(5)

    async def _connect(self):
        try:
            # Create SSL context with certifi's bundle
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            
            async with websockets.connect(RTDS_URL, ssl=ssl_context) as ws:
                self.ws = ws
                self.reconnect_attempts = 0
                success("Connected to RTDS Websocket.")
                
                # Subscribe
                subscription = {
                    'action': 'subscribe',
                    'subscriptions': [{
                        'topic': 'activity',
                        'type': 'trades',
                    }]
                }
                await ws.send(json.dumps(subscription))
                
                async for message in ws:
                    if not self.is_running: break
                    await self._handle_message(message)
                    
        except websockets.exceptions.ConnectionClosed:
            warning("Websocket connection closed.")
        except Exception as e:
            error(f"Websocket error: {e}")

    async def _handle_message(self, message: str):
        if not message: return
        try:
            data = json.loads(message)
            
            if data.get('topic') == 'activity' and data.get('type') == 'trades' and data.get('payload'):
                activity = data['payload']
                
                proxy_wallet = activity.get('proxyWallet', '').lower()
                target_trader = Config.TRADER_ADDRESS.lower()
                
                # Check for EOA match as well just in case
                user_address = activity.get('user', '').lower()
                
                match = False
                if proxy_wallet == target_trader:
                    info(f"MATCH (Proxy): {proxy_wallet}")
                    match = True
                elif user_address == target_trader:
                    info(f"MATCH (EOA): {user_address}")
                    match = True
                
                if match:
                    side = activity.get('side', 'UNKNOWN')
                    trade_detect(f"Detected trade from target: {activity.get('outcome', 'Unknown')} - {side}")
                    await self.queue.put(activity)
                    
        except Exception as e:
            error(f"Error handling message: {e}")
