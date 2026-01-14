import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 1️⃣ GLOBAL HARD RULES
    # Instead of fixed $100, we use these ratios against the current wallet balance (Total Capital)
    CERTAINTY_POOL_RATIO = 0.40
    NORMAL_POOL_RATIO = 0.60
    
    # Cap relative to Total Capital
    MAX_SINGLE_BUCKET_RATIO = 0.10  # 10%
    MAX_SINGLE_MARKET_RATIO = 0.20  # 20%
    
    # 2️⃣ MARKET FILTER

    CATEGORY_FILTER = "Weather"
    CITY_FILTER = "London"
    MARKET_TYPE_FILTER = "Highest temperature"
    RESOLUTION_SOURCE = "official weather station" # Keyword check
    
    # 3️⃣ TRADE CLASSIFICATION
    # Certainty Bet Criteria
    CERTAINTY_PRICE_MAX_CENTS = 95
    CERTAINTY_PRICE_MIN_CENTS = 2
    CERTAINTY_PORTFOLIO_ALLOCATION_THRESHOLD = 0.06 # 6% (Corrected from 8%)
    
    # Normal Bet Criteria
    NORMAL_PRICE_MIN_CENTS = 5
    NORMAL_PRICE_MAX_CENTS = 80
    NORMAL_MIN_ADJACENT_BUCKETS = 2
    NORMAL_MIN_TRADE_SIZE_USD = 5.0 # This matches the Trader's size, not ours. Ours is dynamic.
    NORMAL_MIN_HOURS_BEFORE_RESOLUTION = 3
    
    # 4️⃣ CERTAINTY BET EXECUTION
    CERTAINTY_MAX_PER_BET_RATIO = 0.10 # 10% of Total Capital (capped at pool limits too)
    CERTAINTY_MAX_CONCURRENT_BETS = 3
    CERTAINTY_MAX_SLIPPAGE_CENTS = 1
    CERTAINTY_MIN_POOL_REMAINING_RATIO = 0.05 # Skip if < 5% of pool remaining? (orig: < $5) - let's say 5% of pool allocation
    
    # 5️⃣ NORMAL DISTRIBUTION BET EXECUTION
    NORMAL_MAX_PER_MARKET_RATIO = 0.15
    NORMAL_MAX_PER_BUCKET_RATIO = 0.04
    NORMAL_MAX_SLIPPAGE_CENTS = 2
    NORMAL_POOL_REMAINING_RATIO = 0.15 # similar cap logic
    
    # 6️⃣ IGNORE RULES
    IGNORE_MIN_NOTIONAL_USD = 1.0
    IGNORE_FLIP_WINDOW_MINUTES = 10
    
    # 7️⃣ DAILY CONTROLS
    MAX_DAILY_NEW_EXPOSURE_RATIO = 0.25 # 25% of start-of-day balance
    MAX_DAILY_LOSS_RATIO = 0.15         # 15% of start-of-day balance
    HALT_DURATION_HOURS = 24
    
    # ENV VARS
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    RPC_URL = os.getenv("RPC_URL")
    PROXY_WALLET_ADDRESS = os.getenv("PROXY_WALLET_ADDRESS")
    TRADER_ADDRESS = os.getenv("TRADER_ADDRESS")

    # 8️⃣ RELAY / BUILDER CONFIG
    RELAYER_URL = "https://relayer-v2.polymarket.com"
    POLY_BUILDER_API_KEY = os.getenv("POLY_BUILDER_API_KEY")
    POLY_BUILDER_SECRET = os.getenv("POLY_BUILDER_SECRET")
    POLY_BUILDER_PASSPHRASE = os.getenv("POLY_BUILDER_PASSPHRASE")
    
    @classmethod
    def validate(cls):
        if not cls.PRIVATE_KEY:
            raise ValueError("PRIVATE_KEY not set in .env")
        if not cls.TRADER_ADDRESS:
            raise ValueError("TRADER_ADDRESS not set in .env")
