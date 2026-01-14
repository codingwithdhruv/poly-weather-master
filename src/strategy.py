from datetime import datetime
from .config import Config

class Strategy:
    
    @staticmethod
    def is_valid_market(market_data: dict) -> bool:
        """
        2️⃣ MARKET FILTER (STRICT)
        Category = Weather
        City = London
        Market type = "Highest temperature"
        Resolution source = official weather station
        """
        # Note: API data structure varies, assuming standard Poly keys or derived ones
        category = market_data.get("category", "")
        question = market_data.get("question", "")
        description = market_data.get("description", "")
        

        if category != Config.CATEGORY_FILTER:
            return False
            
        # "London" and "Highest temperature" usually in the question
        if Config.CITY_FILTER not in question:
            return False
        if Config.MARKET_TYPE_FILTER not in question:
            return False
            
        # Resolution source usually in description
        if Config.RESOLUTION_SOURCE not in description.lower():
            return False
            
        return True

    @staticmethod
    def classify_trade(trade_data: dict, market_data: dict, trader_portfolio_alloc: float) -> str:
        """
        3️⃣ TRADE CLASSIFICATION
        Returns: "CERTAINTY", "NORMAL", or None
        """
        price = float(trade_data.get("price", 0))
        size_usd = float(trade_data.get("size_usd", 0)) # Notional size
        
        # 6️⃣ WHAT TO IGNORE (Must also be filtered by flip-detector in Manager)
        if size_usd < Config.IGNORE_MIN_NOTIONAL_USD:
            return None
            
        # 🔴 CERTAINTY BET
        # Price (>= 95¢ OR <= 2¢) AND Trader allocates >= 6% of HIS portfolio
        is_price_extreme = (price >= (Config.CERTAINTY_PRICE_MAX_CENTS / 100.0) or 
                            price <= (Config.CERTAINTY_PRICE_MIN_CENTS / 100.0))
                            
        is_certainty = is_price_extreme and (trader_portfolio_alloc >= Config.CERTAINTY_PORTFOLIO_ALLOCATION_THRESHOLD)
        
        if is_certainty:
            # Safety checks will be done in Main/Manager, but can classify here
            # Skip if < 60 min to resolution
            end_iso = market_data.get("end_date_iso")
            if end_iso:
                seconds_to_res = (datetime.fromisoformat(end_iso) - datetime.utcnow()).total_seconds()
                if seconds_to_res < (60 * 60):
                    return None # Skip late
            
            return "CERTAINTY"
            
        # 🟢 NORMAL BET
        # Price between 5¢ and 80¢
        # Trader buys 2+ adjacent buckets in same market (Checked via Accumulator in Manager)
        # Trade size >= $5 (his size)
        # Occurs ≥ 3 hours before resolution
        
        price_in_range = (Config.NORMAL_PRICE_MIN_CENTS / 100.0) <= price <= (Config.NORMAL_PRICE_MAX_CENTS / 100.0)
        size_ok = size_usd >= Config.NORMAL_MIN_TRADE_SIZE_USD
        
        time_ok = True
        end_iso = market_data.get("end_date_iso")
        if end_iso:
            seconds_to_res = (datetime.fromisoformat(end_iso) - datetime.utcnow()).total_seconds()
            time_ok = seconds_to_res >= (Config.NORMAL_MIN_HOURS_BEFORE_RESOLUTION * 3600)
        
        if price_in_range and size_ok and time_ok:
            # We return NORMAL_CANDIDATE to indicate it needs clustering verification
            return "NORMAL_CANDIDATE"
            
        return None
