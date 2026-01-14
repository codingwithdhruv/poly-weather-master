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
        Config.TRADER_ADDRESS = resolve_to_proxy(Config.TRADER_ADDRESS)
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
                
                classification = Strategy.classify_trade(trade_data, market_data, trader_alloc)
                
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
                    size = account_manager.get_bet_size_certainty(current_balance, opportunities_remaining=3)
                    if size > 0:
                        success(f"EXECUTING CERTAINTY BET: ${size:.2f} on {trade_data['outcome']}")
                        try:
                            # Execute Order
                            order_args = OrderArgs(
                                price=0.99 if trade_data.get('side') == 'BUY' else 0.01, # Example limit price
                                size=size / 0.50, # Rough Estimate of shares, need price. 
                                # Actually, size is USD. Shares = Size / Price.
                                side=BUY if trade_data.get('side') == 'BUY' else SELL,
                                token_id=trade_data.get('asset') # asset/token_id
                            )
                            # Note: Actual price logic needs to be robust (e.g. market price + slippage)
                            # For now leaving as placeholder but with correct types
                            # signed_order = clob_client.create_order(order_args)
                            # resp = clob_client.post_order(signed_order, OrderType.GTC)
                            # success(f"Order Placed: {resp}")
                            account_manager.record_exposure(size)
                        except Exception as e:
                            error(f"Order Execution Failed: {e}")

                    else:
                        warning("Skipping Certainty Bet: Insufficient Pool or Cap hit")

                elif classification == "NORMAL_CANDIDATE":
                    # Add to accumulator
                    is_cluster, bucket_count, exposure = account_manager.accumulator.add_trade(
                        market_id, 
                        trade_data, 
                        account_manager.trader_portfolio_value
                    )
                    
                    if is_cluster:
                        # Use ACTUAL bucket_count for sizing
                        size = account_manager.get_bet_size_normal(current_balance, bucket_count=bucket_count)
                        if size > 0:
                            success(f"EXECUTING NORMAL BET (Cluster Confirmed - Expose {exposure:.2f}): ${size:.2f} on {trade_data['outcome']}")
                            # await clob_client.create_order(...)
                        else:
                            warning("Skipping Normal Bet: Insufficient Pool or Cap hit")
                    else:
                        info(f"Buffered Normal Candidate: Waiting for Cluster/Exposure... (Current Exp: ${exposure:.2f})")
                        
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
