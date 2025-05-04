# generate_token_cache.py

import json
import requests
import gzip

OUTPUT_FILE = "cached_tokens.json"

def add_token_entry(token_map, key, entry):
    if key not in token_map:
        token_map[key] = []
    if entry not in token_map[key]:
        token_map[key].append(entry)

def generate_token_cache():
    print("🔄 Fetching Raydium token list...")

    token_map = {}

    # Add $FATCAT manually
    add_token_entry(token_map, "$FATCAT", {
        "address": "AHdVQs56QpEEkRx6m8yiYYEiqM2sKjQxVd6mGH12pump",
        "decimals": 6
    })

    try:
        url = "https://api.raydium.io/v2/sdk/token/raydium.mainnet.json"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        tokens = (
            data.get("official", []) +
            data.get("unOfficial", []) +
            data.get("unNamed", [])
        )

        for token in tokens:
            symbol = token.get("symbol")
            name = token.get("name")
            address = token.get("mint")
            decimals = token.get("decimals")

            if not symbol or not name or not address or decimals is None:
                continue

            entry = {"address": address, "decimals": decimals}
            add_token_entry(token_map, symbol.upper(), entry)
            add_token_entry(token_map, name.lower(), entry)

        

        with gzip.open(OUTPUT_FILE + ".gz", "wt", encoding="utf-8") as f:
            json.dump(token_map, f)

        print(f"✅ Saved {len(token_map)} symbol/name entries to {OUTPUT_FILE}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    generate_token_cache()
