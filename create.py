# generate_token_cache.py

import json
import requests

OUTPUT_FILE = "cached_tokens.json"

def generate_token_cache():
    print("🔄 Fetching Raydium token list...")

    token_map = {
        "$FATCAT": {
            "address": "AHdVQs56QpEEkRx6m8yiYYEiqM2sKjQxVd6mGH12pump",
            "decimals": 6
        }
    }

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
            if not symbol or not name:
                continue

            symbol = symbol.upper()
            name = name.lower()
            address = token.get("mint")
            decimals = token.get("decimals")

            if not address or decimals is None:
                continue

            token_map[symbol] = {"address": address, "decimals": decimals}
            token_map[name] = {"address": address, "decimals": decimals}

        with open(OUTPUT_FILE, "w") as f:
            json.dump(token_map, f)

        print(f"✅ Saved {len(token_map)} tokens to {OUTPUT_FILE}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    generate_token_cache()
