"""
Create Polymarket CLOB client
Using official py-clob-client library
"""
from typing import Optional, Dict, Any
from web3 import Web3
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

from ..config import Config
from ..utils.logger import info, error

async def is_gnosis_safe(address: str) -> bool:
    """Determines if a wallet is a Gnosis Safe by checking if it has contract code"""
    if not address: return False
    try:
        w3 = Web3(Web3.HTTPProvider(Config.RPC_URL))
        checksum_address = Web3.to_checksum_address(address)
        code = w3.eth.get_code(checksum_address)
        return code != b'0x'
    except Exception as e:
        error(f"Error checking wallet type: {e}")
        return False

async def create_clob_client() -> ClobClient:
    """Create and initialize official ClobClient"""
    chain_id = 137
    host = "https://clob.polymarket.com"
    private_key = Config.PRIVATE_KEY
    
    # Check for Proxy using RelayClient
    from ..clients.relay import RelayClient
    relay_client = RelayClient()
    proxy_address = relay_client.get_expected_safe(Account.from_key(private_key).address)
    
    is_proxy_safe = False
    if proxy_address:
         is_proxy_safe = await is_gnosis_safe(proxy_address)
         if not is_proxy_safe:
             # Assume logical safe if address exists in config/relay detection
             is_proxy_safe = True 

    info(f"Initializing CLOB Client (Safe={is_proxy_safe}, Proxy={proxy_address})...")
    
    # 1. Derive Creds using temp client (L1)
    temp_client = ClobClient(host, key=private_key, chain_id=chain_id)
    try:
        creds = temp_client.create_or_derive_api_creds()
        info("API Credentials derived/created.")
    except Exception as e:
        error(f"Failed to derive API creds: {e}")
        # Only strict error if we cannot proceed?
        # Maybe we should raise?
        raise e

    # 2. Init Full Client
    # Signature Type: 0 (EOA), 1 (Poly Proxy?), 2 (Gnosis Safe)
    sig_type = 2 if is_proxy_safe else 0
    
    client = ClobClient(
        host=host,
        key=private_key,
        chain_id=chain_id,
        creds=creds,
        signature_type=sig_type,
        funder=proxy_address if is_proxy_safe else None
    )
    
    return client
