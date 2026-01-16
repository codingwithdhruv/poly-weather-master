import asyncio
import aiohttp
import time
import ssl
import certifi
import json
from typing import List, Dict, Optional
from ..config import Config
from ..utils.logger import info, error, debug, trade_detect

DATA_API_URL = "https://data-api.polymarket.com/trades"

class TradePoller:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.is_running = False
        self.seen_trade_ids = set()
        self.last_timestamp = int(time.time())  # Track last seen timestamp
        self.POLL_INTERVAL = 3  # 3 seconds (safe within 200 req/10s limit)

    async def start(self):
        self.is_running = True
        info(f"Starting Trade Poller for {Config.TRADER_ADDRESS}...")
        
        # Initial fetch to populate seen_ids without triggering actions
        await self._poll(initial=True)
        
        while self.is_running:
            try:
                await self._poll()
                await asyncio.sleep(self.POLL_INTERVAL)
            except Exception as e:
                error(f"Polling error: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        self.is_running = False
        info("Trade Poller stopped.")

    async def _poll(self, initial: bool = False):
        
        # Create SSL context with certifi
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            # Poll as Maker
            await self._fetch_and_process(session, {"maker": Config.TRADER_ADDRESS}, initial)
            # Poll as Taker
            await self._fetch_and_process(session, {"taker": Config.TRADER_ADDRESS}, initial)

    async def _fetch_and_process(self, session, base_params, initial):
        if not self.is_running: return
        
        # Add common params
        params = base_params.copy()
        params["limit"] = "50"
        
        if self.last_timestamp > 0:
            params["after"] = str(self.last_timestamp - 60) # 1 min buffer

        try:
            async with session.get(DATA_API_URL, params=params) as resp:
                if resp.status != 200:
                    debug(f"API Error {resp.status} for {base_params}: {await resp.text()}")
                    return
                
                trades = await resp.json()
                
                if not trades:
                    return

                # Sort by timestamp ascending to process in order
                # API returns desc usually
                trades.sort(key=lambda x: x.get('timestamp', 0))

                if not initial and not hasattr(self, '_logged_sample'):
                    debug(f"Trade structure: {json.dumps(trades[0], indent=2)}")
                    self._logged_sample = True

                for trade in trades:
                    trade_id = trade.get('id') or f"{trade.get('transactionHash')}-{trade.get('logIndex')}"
                    
                    if trade_id in self.seen_trade_ids:
                        continue
                    
                    self.seen_trade_ids.add(trade_id)
                    
                    # Update last timestamp
                    ts = trade.get('timestamp')
                    if ts and int(ts) > self.last_timestamp:
                        self.last_timestamp = int(ts)
                    
                    if not initial:
                        # Process new trade
                        price = float(trade.get('price', 0))
                        size = float(trade.get('size', 0))
                        
                        # verified mapping from debug output
                        payload = {
                            'conditionId': trade.get('conditionId'), 
                            'outcome': trade.get('outcome'),
                            'side': trade.get('side'),
                            'price': price,
                            'size': size,
                            'size_usd': size * price,
                            'asset': trade.get('asset'),
                            'token_id': trade.get('asset'), # Helper for order creation
                            'timestamp': trade.get('timestamp'),
                            'transactionHash': trade.get('transactionHash'),
                            'title': trade.get('title'),
                            'slug': trade.get('slug'),
                            'proxyWallet': trade.get('proxyWallet')
                        }
                        
                        trade_detect(f"New Trade: {payload['outcome']} @ {payload['price']}")
                        await self.queue.put(payload)
                        
                # Keep set size manageable
                if len(self.seen_trade_ids) > 500:
                    self.seen_trade_ids = set(list(self.seen_trade_ids)[-250:])

        except Exception as e:
            error(f"Fetch error: {e}")
