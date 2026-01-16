import requests
import aiohttp
import time
import ssl
import certifi
from ..config import Config
from .logger import error, info, debug, warning
from .get_my_balance import get_my_balance

GAMMA_API_URL = "https://gamma-api.polymarket.com/markets"
DATA_API_URL = "https://data-api.polymarket.com/positions"

async def fetch_market_data(condition_id: str):
    """Fetch real market data from Gamma API"""
    try:
        # Use simple URL and pass params dict
        url = "https://gamma-api.polymarket.com/markets"
        params = {"condition_id": condition_id}
        
        # Add SSL context with certifi
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status != 200:
                    error(f"Gamma API error {response.status} for {condition_id}")
                    return None
                
                data = await response.json()
                
                # Debug: Log what we actually got
                if isinstance(data, list) and len(data) > 0:
                    m = data[0]
                    # Log snippet of market data to verify it matches trade
                    debug(f"Market Found {condition_id}: {m.get('category')} - {m.get('question')[:40]}...")
                    return m
                else:
                    warning(f"No market data found for {condition_id}")
                    return None
                    
    except Exception as e:
        error(f"Failed to fetch market data for {condition_id}: {e}")
        return None

def get_trader_portfolio_value(address: str) -> float:
    """
    Calculate generic portfolio value (USDC + Positions).
    This is expensive so should be cached/called infrequently.
    """
    try:
        # 1. USDC Balance
        usdc_bal = get_my_balance(address)
        
        # 2. Positions Value
        url = f"{DATA_API_URL}?user={address}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        positions = response.json()
        
        pos_value = 0.0
        if isinstance(positions, list):
            pos_value = sum(float(p.get("currentValue", 0) or 0) for p in positions)
            
        return usdc_bal + pos_value
    except Exception as e:
        error(f"Failed to get portfolio value for {address}: {e}")
        return 1600.0 # Fallback default if API fails (approx value of a small whale)

async def fetch_recent_trades(address: str, limit: int = 5):
    """Fetch recent activity for a user from Data API"""
    try:
        url = "https://data-api.polymarket.com/activity"
        params = {
            "user": address.lower(),
            "limit": str(limit)
        }
        
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    error(f"Activity API error: {resp.status}")
                    return []
                
                data = await resp.json()
                
                if not data:
                    return []
                
                # Filter for trades only (type=TRADE or just has side)
                trades = []
                for item in data:
                    # Activity API returns type='TRADE', side='BUY'/'SELL'
                    if item.get('type') == 'TRADE' or item.get('side') in ['BUY', 'SELL']:
                         trades.append(item)
                         
                return trades[:limit]
                
    except Exception as e:
        error(f"Error fetching activity: {e}")
        return []
