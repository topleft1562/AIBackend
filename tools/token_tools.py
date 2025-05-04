import requests, time

CACHE = {}
TTL = 5 * 60  # Cache TTL: 5 minutes
TOKEN_MAP = {}

def add_token_entry(key, entry):
    if key not in TOKEN_MAP:
        TOKEN_MAP[key] = []
    TOKEN_MAP[key].append(entry)

def load_token_list():
    print("\U0001F504 Loading Raydium token list...")

    add_token_entry("$FATCAT", {
        "address": "AHdVQs56QpEEkRx6m8yiYYEiqM2sKjQxVd6mGH12pump",
        "decimals": 6
    })

    url = "https://api.raydium.io/v2/sdk/token/raydium.mainnet.json"
    res = requests.get(url)

    if res.status_code == 200:
        data = res.json()
        tokens = data.get("official", []) + data.get("unOfficial", []) + data.get("unNamed", [])

        print(f"\U0001F4E6 Found {len(tokens)} total token entries.")

        for token in tokens:
            symbol = token.get("symbol", "").upper()
            name = token.get("name", "").lower()
            address = token.get("mint")
            decimals = token.get("decimals")

            if not address or decimals is None:
                continue

            if symbol:
                add_token_entry(symbol, {"address": address, "decimals": decimals})
            if name:
                add_token_entry(name, {"address": address, "decimals": decimals})

        print(f"✅ Loaded {len(TOKEN_MAP)} unique symbols/names into cache (with duplicates tracked)")
    else:
        print("❌ Failed to fetch token list")

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

def get_token_price(token: str) -> str:
    token_upper = token.upper()
    token_lower = token.lower()

    if token_upper == "SOL":
        sol_price = get_price_cached("SOL", fetch_sol_price)
        return f"1 SOL = ${sol_price:.4f}"

    matches = TOKEN_MAP.get(token_upper) or TOKEN_MAP.get(token_lower)
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

    if results:
        return "\n".join(results)
    else:
        return f"❌ No valid prices found for '{token}'"


