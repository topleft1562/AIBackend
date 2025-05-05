import requests
import time

CACHE = {}
TTL = 5 * 60  # Cache token prices for 5 minutes

TOKEN_REGISTRY = {}  # symbol → { address, decimals }
ADDRESS_REGISTRY = {}  # address → { symbol, decimals }

DEFAULT_TOKENS = [
    {
        "symbol": "$FATCAT",
        "address": "AHdVQs56QpEEkRx6m8yiYYEiqM2sKjQxVd6mGH12pump",
        "decimals": 6
    },
    {
        "symbol": "$ETH",
        "address": "7vfCXTtzZ4a6RZwNEXzq4RZpHZYdHkKp4zj3LZ5D9xwz",  # Wormhole WETH
        "decimals": 8
    },
    {
        "symbol": "$BTC",
        "address": "9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsHtAeTH5YFeJ9E",  # Wormhole WBTC
        "decimals": 8
    },
    {
        "symbol": "$BNB",
        "address": "9gP2kCy3wA1ctvYWQk75guqXuHfrEomqydHLtcTCqiLa",  # Wormhole WBNB
        "decimals": 8
    },
]


# ---- Initialization ----
def normalize(symbol: str):
    base = symbol.strip().upper().lstrip("$")
    return base, f"${base}"

def register_token(symbol, address, decimals):
    base, variant = normalize(symbol)
    entry = {"address": address, "decimals": decimals}
    TOKEN_REGISTRY[base] = entry
    TOKEN_REGISTRY[variant] = entry
    ADDRESS_REGISTRY[address] = {"symbol": variant, "decimals": decimals}

for token in DEFAULT_TOKENS:
    register_token(token["symbol"], token["address"], token["decimals"])


# ---- Price Utilities ----
def fetch_sol_price():
    res = requests.get("https://api.raydium.io/v2/main/price")
    return res.json().get("So11111111111111111111111111111111111111112", 0)

def fetch_token_to_sol_price(mint: str, decimals: int):
    res = requests.get("https://quote-api.jup.ag/v6/quote", params={
        "inputMint": mint,
        "outputMint": "So11111111111111111111111111111111111111112",
        "amount": str(10 ** decimals)
    })
    if res.status_code != 200:
        return 0.0
    return float(res.json().get("outAmount", 0)) / 1e9

def get_price_cached(key, fn):
    now = time.time()
    if key in CACHE and now - CACHE[key]['time'] < TTL:
        return CACHE[key]['value']
    value = fn()
    CACHE[key] = {"value": value, "time": now}
    return value


# ---- Main Functions ----
def get_token_price(token: str) -> str:
    token = token.strip()
    if token.upper() == "SOL":
        price = get_price_cached("SOL", fetch_sol_price)
        return f"1 SOL = ${price:.4f}"

    entry = TOKEN_REGISTRY.get(token.upper())
    if not entry and len(token) >= 32:  # possibly a mint address
        entry = ADDRESS_REGISTRY.get(token)
        if not entry:
            entry = fetch_and_register_token_metadata(token)

    if not entry:
        return f"❌ Token '{token}' not found."

    sol_price = get_price_cached("SOL", fetch_sol_price)
    token_per_sol = fetch_token_to_sol_price(entry["address"], entry["decimals"])
    price = token_per_sol * sol_price
    return f"1 {entry.get('symbol', token)} = ${price:.6f}" if price > 0 else f"❌ No price found for {token}"

def get_token_address(token: str) -> str:
    token = token.strip()
    entry = TOKEN_REGISTRY.get(token.upper())
    if not entry and len(token) >= 32:
        entry = ADDRESS_REGISTRY.get(token)
        if not entry:
            entry = fetch_and_register_token_metadata(token)

    if not entry:
        return f"❌ Token '{token}' not found."

    return f"🔹 Address: {entry['address']} (decimals: {entry['decimals']})"


# ---- Fallback Metadata Fetch ----
def fetch_and_register_token_metadata(mint: str):
    try:
        res = requests.get(f"https://token.jup.ag/info?mint={mint}", timeout=10)
        if res.status_code == 200:
            data = res.json()
            symbol = data.get("symbol", mint[:4]).upper()
            decimals = data.get("decimals", 6)
            register_token(symbol, mint, decimals)
            return {"address": mint, "decimals": decimals, "symbol": symbol}
    except Exception:
        pass
    return None
