import json
import time
import os
from decimal import Decimal
from .config import Config
from .utils.logger import info

STATE_FILE = "bot_state.json"

class MarketAccumulator:
    """
    [LEGACY / UNUSED] 
    Buffers trades to detect clusters. 
    Not used in current INVENTORY MIRRORING strategy (Mode A is immediate).
    Retained for potential reversion to cluster-based logic.
    """
    def __init__(self):
        self.buffers = {} # market_id -> list of trades
        
    def add_trade(self, market_id: str, trade: dict, trader_portfolio_value: float) -> tuple[bool, int, float]:
        """
        Add trade and check if cluster condition is met.
        Returns (is_triggered, bucket_count, total_exposure_usd)
        """
        if market_id not in self.buffers:
            self.buffers[market_id] = []
            
        # Append trade with timestamp
        trade['added_at'] = time.time()
        self.buffers[market_id].append(trade)
        
        # Prune old trades (> 60 mins)
        cutoff = time.time() - (60 * 60)
        self.buffers[market_id] = [t for t in self.buffers[market_id] if t['added_at'] > cutoff]
        
        # Check conditions
        trades = self.buffers[market_id]
        
        # 1. Bucket Count (>= 2 unique buckets)
        unique_buckets = set(t['outcome'] for t in trades)
        bucket_count = len(unique_buckets)
        
        # 2. Total Exposure (>= 4% of trader portfolio)
        total_exposure = sum(float(t.get('size_usd', 0)) for t in trades)
        exposure_threshold = trader_portfolio_value * 0.04
        
        if bucket_count >= Config.NORMAL_MIN_ADJACENT_BUCKETS and total_exposure >= exposure_threshold:
             return True, bucket_count, total_exposure
             
        return False, bucket_count, total_exposure

class AccountManager:
    def __init__(self, web3_client=None):
        self.web3_client = web3_client
        self.state = self._load_state()
        self.accumulator = MarketAccumulator()
        self.recent_trades = {} 
        self.trader_portfolio_value = 0 # Cache this
        self.last_portfolio_update = 0
        
    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "daily_start_balance": 0,
            "current_loss": 0,
            "current_exposure": 0,
            "last_reset_time": 0,
            "pools": {
                "certainty": 0,
                "normal": 0
            },
            "market_exposures": {} # market_id -> float (usd exposure)
        }
        
    def _save_state(self):
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)

    def is_flip(self, market_id: str, outcome: str, side: str) -> bool:
        key = (market_id, outcome)
        now = time.time()
        
        if key in self.recent_trades:
            last_side, last_time = self.recent_trades[key]
            if last_side != side and (now - last_time) < (Config.IGNORE_FLIP_WINDOW_MINUTES * 60):
                return True 
        
        self.recent_trades[key] = (side, now)
        return False

    def update_balance(self, current_balance: float):
        now = time.time()
        if now - self.state["last_reset_time"] > Config.HALT_DURATION_HOURS * 3600:
            self.state["daily_start_balance"] = current_balance
            self.state["current_loss"] = 0
            self.state["current_exposure"] = 0
            self.state["last_reset_time"] = now
            self.state["pools"]["certainty"] = current_balance * Config.CERTAINTY_POOL_RATIO
            self.state["pools"]["normal"] = current_balance * Config.NORMAL_POOL_RATIO
            self._save_state()
        return self.state

    def check_daily_guardrails(self) -> bool:
        start_bal = self.state["daily_start_balance"]
        if start_bal == 0: return True
        max_loss = start_bal * Config.MAX_DAILY_LOSS_RATIO
        if self.state["current_loss"] >= max_loss:
            return False
        return True

    def record_exposure(self, amount: float, market_id: str = None):
        self.state["current_exposure"] += amount
        
        if market_id:
            if "market_exposures" not in self.state:
                self.state["market_exposures"] = {}
            
            curr = self.state["market_exposures"].get(market_id, 0.0)
            self.state["market_exposures"][market_id] = curr + amount
            
        self._save_state()

    def check_market_cap(self, market_id: str, proposed_amount: float, total_balance: float) -> bool:
        if "market_exposures" not in self.state:
             self.state["market_exposures"] = {}
             
        current_market_exp = self.state["market_exposures"].get(market_id, 0.0)
        max_market_exp = total_balance * Config.MAX_SINGLE_MARKET_RATIO
        
        if (current_market_exp + proposed_amount) > max_market_exp:
            return False
        return True
        
    def get_bet_size_certainty(self, total_balance: float, opportunities_remaining: int) -> float:
        max_bet = total_balance * Config.CERTAINTY_MAX_PER_BET_RATIO
        pool_remaining = self.state["pools"]["certainty"]
        
        if pool_remaining < (total_balance * Config.CERTAINTY_MIN_POOL_REMAINING_RATIO):
            return 0.0
            
        dynamic_size = pool_remaining / max(1, opportunities_remaining)
        return min(max_bet, dynamic_size)
    
    def get_bet_size_normal(self, total_balance: float, bucket_count: int) -> float:
        """
        Divide budget by ACTUAL cluster bucket count
        """
        max_market = total_balance * Config.NORMAL_MAX_PER_MARKET_RATIO
        pool_remaining = self.state["pools"]["normal"]
        
        market_budget = min(max_market, pool_remaining)
        return market_budget / max(1, bucket_count)
