import requests
import aiohttp
import time
from ..config import Config
from .logger import error, info
from .get_my_balance import get_my_balance

GAMMA_API_URL = "https://gamma-api.polymarket.com/markets"
DATA_API_URL = "https://data-api.polymarket.com/positions"

async def fetch_market_data(condition_id: str):
    """Fetch real market data from Gamma API"""
    try:
        url = f"{GAMMA_API_URL}?condition_id={condition_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                response.raise_for_status()
                data = await response.json()
                
                if isinstance(data, list) and len(data) > 0:
                    return data[0] # Gamma returns a list
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
