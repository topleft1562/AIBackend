import json
import requests
import time

CACHE = {}
TTL = 5 * 60  # Cache TTL: 5 minutes

# Dynamic token mappings
TOKEN_MAP = {}
ADDRESS_MAP = {}  # mint address -> { symbol, decimals }

FATCAT_ENTRY = {
    "address": "AHdVQs56QpEEkRx6m8yiYYEiqM2sKjQxVd6mGH12pump",
    "decimals": 6
}

def add_symbol_variants(symbol: str, entry: dict):
    """Add multiple variations of the token symbol to TOKEN_MAP."""
    variants = {
        symbol.upper(),
        symbol.lower(),
        symbol.upper().lstrip("$"),
        symbol.lower().lstrip("$"),
        f"${symbol.upper().lstrip('$')}"
    }
    for variant in variants:
        if variant not in TOKEN_MAP:
            TOKEN_MAP[variant] = []
        if entry not in TOKEN_MAP[variant]:
            TOKEN_MAP[variant].append(entry)


# Add FATCAT by default
add_symbol_variants("$FATCAT", FATCAT_ENTRY)

# Add direct mint-to-symbol entry to ADDRESS_MAP
ADDRESS_MAP[FATCAT_ENTRY["address"]] = {
    "symbol": "$FATCAT",
    "decimals": FATCAT_ENTRY["decimals"]
}


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
            add_symbol_variants(symbol, {"address": mint, "decimals": decimals})
            return symbol, decimals
    except Exception:
        pass
    return mint[:4].upper(), 6  # fallback


def find_token_matches(symbol: str):
    symbol = symbol.strip()
    keys_to_try = {
        symbol,
        symbol.upper(),
        symbol.lower(),
        symbol.upper().lstrip("$"),
        symbol.lower().lstrip("$"),
        f"${symbol.upper().lstrip('$')}"
    }
    for key in keys_to_try:
        if key in TOKEN_MAP:
            return key, TOKEN_MAP[key]
    return None, None


def get_token_price(token: str) -> str:
    token_upper = token.upper()
    if token_upper == "SOL":
        sol_price = get_price_cached("SOL", fetch_sol_price)
        return f"1 SOL = ${sol_price:.4f}"

    _, matches = find_token_matches(token)

    # If not found, maybe it's a mint address
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
    _, matches = find_token_matches(token)

    if not matches and len(token) >= 32:
        if token in ADDRESS_MAP:
            matches = [{"address": token, "decimals": ADDRESS_MAP[token]["decimals"]}]
        else:
            symbol, decimals = fetch_token_metadata(token)
            matches = [{"address": token, "decimals": decimals}]

    if not matches:
        return f"❌ Token '{token}' not found."

    results = []
    for entry in matches:
        results.append(f"🔹 Address: {entry['address']} (decimals: {entry['decimals']})")

    return "\n".join(results)
