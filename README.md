# Poly Weather Master Bot

A specialized trading bot designed to monitor a target trader on Polymarket and execute copy trades based on specific strategies and risk management rules.

## Features

- **Real-time Monitoring**: Tracks a specific target trader's activity via WebSocket.
- **Automated Copy Trading**: Automatically executes trades when the target trader's activity matches defined criteria ("Certainty" or "Normal" bets).
- **Risk Management**: Includes daily loss limits and exposure caps to protect your portfolio.
- **Proxy Resolution**: Automatically resolves the target trader's Externally Owned Account (EOA) to their Proxy Wallet address for accurate tracking.
- **Gasless Operations**: potentially utilizes relay clients for efficient transaction management.

## Prerequisites

- **Python 3.10+**: Ensure you have a compatible version of Python installed.
- **pip**: Python package installer.
- **Polygon Wallet**: A funded wallet on the Polygon network (for gas and trading capital).

## Installation

1.  **Clone the Repository**
    ```bash
    git clone <repository_url>
    cd poly-weather-master
    ```

2.  **Set Up a Virtual Environment (Recommended)**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Create Environment File**
    Copy the example environment file to create your local interface configuration.
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env`**
    Open `.env` in your text editor and fill in the required details:

    *   `PRIVATE_KEY`: Your wallet's private key (without the `0x` prefix). **Keep this secret!**
    *   `RPC_URL`: A reliable Polygon RPC URL (e.g., `https://polygon-rpc.com`).
    *   `TRADER_ADDRESS`: The wallet address of the trader you want to track (EOA). The bot will automatically resolve this to their proxy address.
    *   `PROXY_WALLET_ADDRESS`: (Optional) Your own proxy wallet address if you are using one.
    *   `MAX_DAILY_LOSS`: Maximum percentage of daily loss allowed before halting (e.g., `15`).
    *   `MAX_DAILY_NEW_EXPOSURE`: Maximum percentage of portfolio allowed for new positions daily (e.g., `25`).

## Usage

To start the bot, run the following command from the root directory of the project:

```bash
python3 -m src.main
```

## Structure

- **src/main.py**: The entry point of the application. Handles initialization and the main event loop.
- **src/config.py**: Manages configuration and environment variables.
- **src/monitor.py**: Handles WebSocket connections and monitors the target trader.
- **src/strategy.py**: Contains logic for classifying trades and market validation.
- **src/manager.py**: Manages account balance, exposure, and risk checks.

## Disclaimer

This software is for educational purposes only. Trading cryptocurrencies and prediction markets involves significant risk. The authors are not responsible for any financial losses incurred while using this bot.
