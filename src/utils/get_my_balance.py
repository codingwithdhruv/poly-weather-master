from web3 import Web3
from ..config import Config

USDC_CONTRACT_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
USDC_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    }
]

def get_my_balance(address: str) -> float:
    """Get USDC balance for an address on Polygon"""
    try:
        w3 = Web3(Web3.HTTPProvider(Config.RPC_URL))
        checksum_address = Web3.to_checksum_address(address)
        checksum_usdc = Web3.to_checksum_address(USDC_CONTRACT_ADDRESS)
        
        contract = w3.eth.contract(address=checksum_usdc, abi=USDC_ABI)
        balance_wei = contract.functions.balanceOf(checksum_address).call()
        
        return float(balance_wei) / 10**6
    except Exception as e:
        print(f"Error fetching balance for {address}: {e}")
        return 0.0
