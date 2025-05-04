import json
import requests
import time

CACHE = {}
TTL = 5 * 60  # Cache TTL: 5 minutes

# Dynamic token mappings
TOKEN_MAP = {
    "$FATCAT": [{"address": "AHdVQs56QpEEkRx6m8yiYYEiqM2sKjQxVd6mGH12pump", "decimals": 6}]
}
ADDRESS_MAP = {}  # mint address -> { symbol, decimals }

def add_token_entry(symbol: str, entry: dict):
    if symbol not in TOKEN_MAP:
        TOKEN_MAP[symbol] = []
    if entry not in TOKEN_MAP[symbol]:
        TOKEN_MAP[symbol].append(entry)

def get_price_cached(symbol, fetch_fn):
    now = time.time()
    if symbol in CACHE and now - CACHE[symbol]['time'] < TTL:
        return CACHE[symbol]['value']
    value = fetch_fn()
    CACHE[symbol] = {'value': value, 'time': now}
    return value

def fetch_sol_price():
    res = requests.get("https://api.raydium.io/v2/main/price")
    return res.json().get("So11111111111111111111111111111111111111112", 0)

def fetch_token_to_sol_price(input_mint: str, decimals: int):
    amount = 10 ** decimals
    res = requests.get("https://quote-api.jup.ag/v6/quote", params={
        "inputMint": input_mint,
        "outputMint": "So11111111111111111111111111111111111111112",
        "amount": str(amount)
    })
    if res.status_code != 200:
        return 0.0
    data = res.json()
    return float(data["outAmount"]) / 1e9

def fetch_token_metadata(mint: str):
    try:
        res = requests.get(f"https://token.jup.ag/info?mint={mint}", timeout=10)
        if res.status_code == 200:
            data = res.json()
            symbol = data.get("symbol", mint[:4]).upper()
            decimals = data.get("decimals", 6)
            ADDRESS_MAP[mint] = {"symbol": symbol, "decimals": decimals}
            add_token_entry(symbol, {"address": mint, "decimals": decimals})
            return symbol, decimals
    except Exception:
        pass
    return mint[:4].upper(), 6  # fallback dummy

def get_token_price(token: str) -> str:
    token_upper = token.upper()
    token_lower = token.lower()

    if token_upper == "SOL":
        sol_price = get_price_cached("SOL", fetch_sol_price)
        return f"1 SOL = ${sol_price:.4f}"

    matches = TOKEN_MAP.get(token_upper) or TOKEN_MAP.get(token_lower)

    # If not found, check if it's a mint address
    if not matches and len(token) >= 32:
        if token in ADDRESS_MAP:
            info = ADDRESS_MAP[token]
            matches = [{"address": token, "decimals": info["decimals"]}]
            token_upper = info["symbol"]
        else:
            symbol, decimals = fetch_token_metadata(token)
            matches = [{"address": token, "decimals": decimals}]
            token_upper = symbol

    if not matches:
        return f"❌ Token '{token}' not found."

    if not isinstance(matches, list):
        matches = [matches]

    sol_price = get_price_cached("SOL", fetch_sol_price)
    results = []

    for entry in matches:
        try:
            token_per_sol = fetch_token_to_sol_price(entry["address"], entry["decimals"])
            token_price = token_per_sol * sol_price
            if token_price > 0:
                results.append(f"1 {token_upper} ({entry['address'][:4]}...): ${token_price:.6f}")
        except Exception:
            continue

    return "\n".join(results) if results else f"❌ No valid prices found for '{token}'"

def get_token_address(token: str) -> str:
    token_upper = token.upper()
    token_lower = token.lower()

    matches = TOKEN_MAP.get(token_upper) or TOKEN_MAP.get(token_lower)

    if not matches and len(token) >= 32:
        if token in ADDRESS_MAP:
            matches = [{"address": token, "decimals": ADDRESS_MAP[token]["decimals"]}]
        else:
            symbol, decimals = fetch_token_metadata(token)
            matches = [{"address": token, "decimals": decimals}]

    if not matches:
        return f"❌ Token '{token}' not found."

    if not isinstance(matches, list):
        matches = [matches]

    results = []
    for entry in matches:
        address = entry["address"]
        decimals = entry["decimals"]
        results.append(f"🔹 Address: {address} (decimals: {decimals})")

    return "\n".join(results)
