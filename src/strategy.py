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
    def classify_trade(trade_data: dict, market_data: dict, trader_portfolio_alloc: float) -> tuple[str, str]:
        """
        3️⃣ TRADE CLASSIFICATION
        Returns: (Classification, Reason)
        Classification: "CERTAINTY", "INVENTORY", or None
        """
        price = float(trade_data.get("price", 0))
        size_usd = float(trade_data.get("size_usd", 0)) # Notional size
        
        # 6️⃣ WHAT TO IGNORE (Must also be filtered by flip-detector in Manager)
        if size_usd < Config.IGNORE_MIN_NOTIONAL_USD:
            return None, f"Size ${size_usd:.2f} < ${Config.IGNORE_MIN_NOTIONAL_USD} min"
            
        # 🟢 INVENTORY MODE (Mode A) - The Bread & Butter
        # Price 5c - 85c (Config.NORMAL_PRICE_MAX_CENTS)
        # Trader size <= 5% (Raised from 1%) of HIS portfolio (small drip)
        price_inventory = (Config.NORMAL_PRICE_MIN_CENTS / 100.0) <= price <= (Config.NORMAL_PRICE_MAX_CENTS / 100.0)
        alloc_inventory = trader_portfolio_alloc <= 0.05 # Raised to 5% to catch larger drips ($50 on $3.5k is ~1.4%)
        
        if price_inventory and alloc_inventory:
            # We treat this as an "INVENTORY" trade to be mirrored immediately (dripped)
            return "INVENTORY", "Matches Inventory criteria"
            
        # 🔴 CERTAINTY MODE (Mode B) - The "Danger Zone"
        # Price > 95c or < 5c OR huge size (> 10%)
        # For this trader, we want to be EXTREMELY careful here.
        
        is_price_extreme = (price >= (Config.CERTAINTY_PRICE_MAX_CENTS / 100.0) or 
                            price <= (Config.CERTAINTY_PRICE_MIN_CENTS / 100.0))
                            
        is_huge_size = (trader_portfolio_alloc >= Config.CERTAINTY_PORTFOLIO_ALLOCATION_THRESHOLD)
        
        # ISSUE 2 FIX: Require BOTH Price Extreme AND Huge Size
        if is_price_extreme and is_huge_size:
            # Skip if < 60 min to resolution
            end_iso = market_data.get("end_date_iso")
            if end_iso:
                seconds_to_res = (datetime.fromisoformat(end_iso) - datetime.utcnow()).total_seconds()
                if seconds_to_res < (60 * 60):
                    return None, "Certainty candidate but < 60 mins to resolution"
            
            return "CERTAINTY", "Matches Certainty criteria (Extreme Price + Huge Size)"
            
        # Generate skip reason
        reason = []
        if not price_inventory: reason.append(f"Price {price:.2f} not in Inventory range {Config.NORMAL_PRICE_MIN_CENTS/100:.2f}-{Config.NORMAL_PRICE_MAX_CENTS/100:.2f}")
        if not alloc_inventory: reason.append(f"Alloc {trader_portfolio_alloc*100:.2f}% > 5% limit")
        if not (is_price_extreme and is_huge_size): reason.append("Not certain (Price/Size mismatch)")
        
        return None, "; ".join(reason)
