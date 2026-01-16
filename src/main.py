import asyncio
import time
from .config import Config
from .manager import AccountManager
from .strategy import Strategy
from .monitor import TradeMonitor
from .utils.logger import header, info, warning, error, success
from .utils.create_clob_client import create_clob_client
from .utils.api_helper import fetch_market_data, get_trader_portfolio_value
from .clients.relay import RelayClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

async def main():
    header("POLY WEATHER MASTER BOT")
    
    try:
        Config.validate()
        # Resolve Trader EOA -> Proxy for RTDS Monitoring
        from .utils.resolve_proxy import resolve_to_proxy
        target_proxy = resolve_to_proxy(Config.TRADER_ADDRESS)
        # We track the proxy if resolved, otherwise fallback to EOA but monitoring might be spotty without Polling fix
        Config.TRADER_ADDRESS = target_proxy # Update config to track the correct address
        info(f"Configuration validated. Tracking: {Config.TRADER_ADDRESS}")
    except Exception as e:
        error(f"Configuration error: {e}")
        return

    # Initialize Relay Client (for safe management/gasless ops)
    relay_client = RelayClient()
    info("Initialized Relay Client.")

    account_manager = AccountManager()
    
    # Initial Portfolio Value Fetch
    info("Fetching Trader Portfolio Value...")
    account_manager.trader_portfolio_value = get_trader_portfolio_value(Config.TRADER_ADDRESS)
    account_manager.last_portfolio_update = time.time()
    info(f"Trader Portfolio Value: ${account_manager.trader_portfolio_value:.2f}")

    trade_queue = asyncio.Queue()
    monitor = TradeMonitor(trade_queue)
    
    # Create CLOB Client (uses Relay logic internally for proxy detection now)
    clob_client = await create_clob_client()
    
    if not account_manager.check_daily_guardrails():
        error(f"Daily guardrails triggered. Halting trading.")
        return

    monitor_task = asyncio.create_task(monitor.start())
    info("State: WAITING FOR TRADES...")
    
    try:
        while True:
            # Update trader portfolio cached value every hour
            if time.time() - account_manager.last_portfolio_update > 3600:
                 account_manager.trader_portfolio_value = get_trader_portfolio_value(Config.TRADER_ADDRESS)
                 account_manager.last_portfolio_update = time.time()
            
            trade_data = await trade_queue.get()
            
            try:
                # 1. Fetch Real Market Data
                market_id = trade_data.get('conditionId')
                if not market_id:
                     warning("Trade missing conditionId")
                     continue
                     
                market_data = await fetch_market_data(market_id)
                if not market_data:
                    warning(f"Could not fetch market data for {market_id}")
                    continue
                
                # Debug logging for filter
                info(f"Trade received: {trade_data.get('outcome')} on market {market_id}")
                info(f"Market category: {market_data.get('category')}, question: {market_data.get('question')[:50]}")

                # 2. Market Filter
                if not Strategy.is_valid_market(market_data):
                    info(f"Skipping trade: Invalid market category/question")
                    continue
                
                # Flip Protection
                if account_manager.is_flip(
                    market_id=market_id,
                    outcome=trade_data.get('outcome', ''),
                    side=trade_data.get('side', '')
                ):
                    warning(f"Skipping trade: FLIP DETECTED on {trade_data.get('outcome')}")
                    continue

                # 3. Classify
                trade_size_usd = float(trade_data.get('size_usd', 0))
                if trade_size_usd == 0:
                     trade_size_usd = float(trade_data.get('size', 0)) * float(trade_data.get('price', 0))
                     trade_data['size_usd'] = trade_size_usd
                
                trader_alloc = trade_size_usd / max(1, account_manager.trader_portfolio_value)
                
                classification, reason = Strategy.classify_trade(trade_data, market_data, trader_alloc)
                
                if classification:
                    info(f"Trade CLASSIFIED as {classification}: {reason}")
                else:
                    info(f"Trade SKIPPED: {reason}")
                    trade_queue.task_done()
                    continue
                
                from .utils.get_my_balance import get_my_balance
                current_balance = get_my_balance(Config.PROXY_WALLET_ADDRESS)
                
                # Low Balance Check
                if current_balance < 5.0: # Minimum $5 to operate
                     warning(f"Low Balance (${current_balance:.2f}). Skipping trades.")
                     # We can choose to halt or just skip
                     # For now, just skip logic
                     trade_queue.task_done()
                     continue

                account_manager.update_balance(current_balance)
                
                if classification == "CERTAINTY":
                    # For Certainty Mode B, we are now extremely cautious
                    # Max size is HARD CAPPED at MAX_SINGLE_TRADE_RATIO (0.25%)
                    # We treat it same as max inventory drip
                    
                    max_drip = current_balance * Config.MAX_SINGLE_TRADE_RATIO
                    size = max_drip # Always just drip, never go big
                    
                    if size > 0:
                        success(f"EXECUTING CERTAINTY BET (CAPPED): ${size:.2f} on {trade_data['outcome']}")
                        try:
                            price = float(trade_data.get('price', 0.50))
                            shares_size = size / price
                            
                            order_args = OrderArgs(
                                price=price,
                                size=shares_size, 
                                side=BUY if trade_data.get('side') == 'BUY' else SELL,
                                token_id=trade_data.get('asset')
                            )
                            
                            tick_size = market_data.get("minimum_tick_size", "0.01")
                            neg_risk = market_data.get("neg_risk", False)

                            signed_order = clob_client.create_order(
                                order_args, 
                                options={"tick_size": str(tick_size), "neg_risk": neg_risk}
                            )
                            
                            if not account_manager.check_market_cap(market_id, size, current_balance):
                                warning(f"Skipping Certainty Bet: Market Cap hit for {market_id}")
                                trade_queue.task_done()
                                continue

                            resp = clob_client.post_order(signed_order, OrderType.GTC)
                            success(f"Order Placed (Certainty Capped): {resp}")
                            account_manager.record_exposure(size, market_id)
                        except Exception as e:
                            error(f"Order Execution Failed: {e}")

                elif classification == "INVENTORY":
                    # INVENTORY MODE (Mode A) implementation
                    # No accumulator wait - immediate execution
                    # Size capped at 0.25% of OUR portfolio
                    
                    max_drip = current_balance * Config.MAX_SINGLE_TRADE_RATIO
                    # Optionally scale down if pool is low, but usually just fixed drip
                    size = max_drip
                    
                    if size > 0:
                        success(f"EXECUTING INVENTORY BET: ${size:.2f} on {trade_data['outcome']}")
                        try:
                            # Use Limit order at trade price
                            price = float(trade_data.get('price', 0.50))
                            shares_size = size / price
                            
                            order_args = OrderArgs(
                                price=price,
                                size=shares_size, # Shares
                                side=BUY if trade_data.get('side') == 'BUY' else SELL,
                                token_id=trade_data.get('asset')
                            )
                            
                            tick_size = market_data.get("minimum_tick_size", "0.01")
                            neg_risk = market_data.get("neg_risk", False)

                            signed_order = clob_client.create_order(
                                order_args,
                                options={"tick_size": str(tick_size), "neg_risk": neg_risk}
                            )
                            
                            if not account_manager.check_market_cap(market_id, size, current_balance):
                                warning(f"Skipping Inventory Bet: Market Cap hit for {market_id}")
                                trade_queue.task_done()
                                continue

                            resp = clob_client.post_order(signed_order, OrderType.GTC)
                            success(f"Order Placed (Inventory): {resp}")
                            
                            # Add to accumulator just for tracking/logging if relevant later, 
                            # but we don't block on it.
                            # We can also track exposure here.
                            account_manager.record_exposure(size, market_id)
                            
                        except Exception as e:
                            error(f"Inventory Order Failed: {e}")
                    else:
                        warning("Skipping Inventory Bet: Size near zero")

            except Exception as e:
                error(f"Error processing trade: {e}")
            finally:
                trade_queue.task_done()
            
    except KeyboardInterrupt:
        info("Stopping bot...")
    finally:
        await monitor.stop()
        await monitor_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
