import requests
from .logger import info, error

def resolve_to_proxy(address: str) -> str:
    """
    Resolves an input address (EOA or Proxy) to its Proxy Wallet Address.
    If the input is already a proxy or has no public profile, checks Gamma.
    """
    try:
        url = f"https://gamma-api.polymarket.com/public-profile?address={address}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 404:
            # Maybe it's already a proxy or just has no profile? 
            # We assume the user provided the correct address if 404.
            info(f"Address {address} profile not found (404). Using as-is.")
            return address
            
        data = response.json()
        proxy = data.get("proxyWallet")
        
        if proxy and proxy.lower() != address.lower():
            info(f"Resolved EOA {address} -> Proxy {proxy}")
            return proxy
        
        return address
        
    except Exception as e:
        error(f"Failed to resolve proxy for {address}: {e}")
        return address
