import asyncio
import aiohttp
import time
import ssl
import certifi
import json
from typing import List, Dict, Optional
from ..config import Config
from ..utils.logger import info, error, debug, trade_detect

ACTIVITY_API_URL = "https://data-api.polymarket.com/activity"

class TradePoller:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.is_running = False
        self.seen_ids = set()
        self.POLL_INTERVAL = 3

    async def start(self):
        self.is_running = True
        info(f"Starting Trade Poller for {Config.TRADER_ADDRESS}...")
        
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
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        params = {
            "user": Config.TRADER_ADDRESS.lower(),
            "limit": "50"
        }
        
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(ACTIVITY_API_URL, params=params) as resp:
                    if resp.status != 200:
                        debug(f"API Error {resp.status}")
                        return
                    
                    activities = await resp.json()
                    
                    if not activities:
                        return
                    
                    # Filter for trades only
                    trades = []
                    for a in activities:
                        if a.get('type') == 'TRADE' or a.get('side') in ['BUY', 'SELL']:
                            trades.append(a)
                    
                    if not initial and trades:
                        # Find new ones for debug
                        new_trades = [t for t in trades if (t.get('id') or t.get('transactionHash')) not in self.seen_ids]
                        if new_trades:
                            debug(f"Found {len(new_trades)} new trades for target")
                    
                    # Sort by timestamp ascending to process oldest first
                    trades.sort(key=lambda x: x.get('timestamp', 0))

                    for trade in trades:
                        trade_id = trade.get('id') or trade.get('transactionHash')
                        
                        if trade_id in self.seen_ids:
                            continue
                        
                        self.seen_ids.add(trade_id)
                        
                        if not initial:
                            # Map activity fields to trade payload
                            # Activity data has 'side': 'BUY'/'SELL'
                            side_val = trade.get('side') or trade.get('type', '')
                            
                            payload = {
                                'conditionId': trade.get('conditionId'), 
                                'outcome': trade.get('outcome'),
                                'side': side_val.upper(),
                                'price': float(trade.get('price', 0)),
                                'size': float(trade.get('size', 0)),
                                'size_usd': float(trade.get('usdcSize', 0)), # Activity API uses usdcSize
                                'asset': trade.get('asset'),
                                'token_id': trade.get('asset'), 
                                'timestamp': trade.get('timestamp'),
                                'transactionHash': trade.get('transactionHash'),
                                'title': trade.get('title', ''),
                                'slug': trade.get('slug', ''),
                                'proxyWallet': Config.TRADER_ADDRESS # We know it's them
                            }
                            
                            trade_detect(f"New Trade: {payload['title'][:40]} | {payload['outcome']} @ {payload['price']}")
                            await self.queue.put(payload)
                    
                    # Keep set size manageable
                    if len(self.seen_ids) > 500:
                        self.seen_ids = set(list(self.seen_ids)[-250:])
                        
        except Exception as e:
            error(f"Fetch error: {e}")
