# Poly Weather Master Bot

A specialized trading bot designed to mirror the inventory accumulation strategy of a specific Polymarket whale, specifically targeting "London Weather" markets.

## Strategy Overview: "Inventory Mirroring"

The bot implements a sophisticated **Inventory Mirroring** strategy (`src/strategy.py`) rather than simple copy trading. It identifies two distinct modes of operation from the target trader:

### 1. Mode A: Inventory Building (The "Bread & Butter")
*   **Goal**: Mirror the target's accumulation of contracts in the 5¢ - 85¢ range.
*   **Trigger**: Any trade by the target < 5% of their portfolio size and within the price range.
*   **Resolution**: **Immediate Execution**. We do not wait for clusters. We "drip" buy alongside them.
*   **Sizing**: Strictly capped at **0.25%** of *your* bot's portfolio per trade.
*   **Allocation**: 90% of your capital is reserved for this mode.

### 2. Mode B: Certainty Bets (Risk Mitigation)
*   **Trigger**: Extreme conviction trades (Price > 95¢ or < 5¢ **AND** Size > 10% of target portfolio).
*   **Execution**: **Safety Cap Enabled**. We execute these but *strictly capped* at the same 0.25% small size.
*   **Why**: To avoid "following the whale off a cliff" on their high-risk/private-info bets while still maintaining exposure.

## Key Features

- **Robust Polling**: Uses `aiohttp` to poll the Polymarket Data API every 3 seconds, querying both `maker` and `taker` history to capture 100% of activity.
- **Timestamp Filtering**: Efficiently queries only new trades using the `after` timestamp parameter.
- **Smart Filtering**:
    - **London Weather Only**: Validates category, city, and resolution source ("london city airport").
    - **Dead Zone Avoidance**: Skips late-stage trades between 85¢-95¢ where convexity is poor.
- **Risk Management**:
    - **Per-Market Cap**: Hard limit of **3%** portfolio exposure per single market to prevent over-accumulation.
    - **Flip Protection**: minimal 3-minute window to filter noise vs legitimate inventory management.
    - **Daily Guardrails**: loss limits and exposure caps.

## Prerequisites

- **Python 3.10+**
- **Polygon Wallet**: Funded with `USDC.e` (Bridged USDC) and `POL` (Matic) for gas.

## Installation

1.  **Clone the Repository**
    ```bash
    git clone <repository_url>
    cd poly-weather-master
    ```

2.  **Install System Deps (Linux/Mac)**
    ```bash
    # Mac
    brew install python3
    
    # Linux
    sudo apt update && sudo apt install -y python3-venv python3-pip
    ```

3.  **Set Up Virtual Environment**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

4.  **Install Dependencies**
    ```bash
    pip install --upgrade pip
    pip install -r requirements.txt
    ```

## Configuration

1.  **Create `.env`**
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env`**
    *   `PRIVATE_KEY`: Your wallet private key.
    *   `RPC_URL`: Polygon RPC (e.g., `https://polygon-rpc.com`).
    *   `TRADER_ADDRESS`: Target whale address.
    *   `PROXY_WALLET_ADDRESS`: Your Gnosis Safe / Proxy address (if using Relayer).

## Usage

Run the bot:
```bash
python3 -m src.main
```

### Understanding Logs

The bot provides verbose logging to explain every decision:
*   `[DETECTED] New Trade`: Poller found a trade.
*   `Trade CLASSIFIED as INVENTORY`: Matches criteria, will execute.
*   `Trade SKIPPED`: Log explains why (e.g., `Alloc 10.5% > 5% limit`, `Price 98.00 not in Inventory range`).
*   `EXECUTING INVENTORY BET`: Order placed.

## Deployment (Supervisor)

For 24/7 operation on a VPS:

```ini
[program:poly-weather-master]
command=/path/to/venv/bin/python -m src.main
directory=/path/to/poly-weather-master
autostart=true
autorestart=true
stderr_logfile=/path/to/logs/err.log
stdout_logfile=/path/to/logs/out.log
environment=PYTHONUNBUFFERED="1"
```

## Disclaimer

This software is for educational purposes only. Prediction markets carry significant risk. Use at your own discretion.
