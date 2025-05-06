from tools.db import coins, coinstatuses, scratchhistories, spinhistories, solforge_users

def query_mongo(
    collection: str,
    filter: dict = {},
    sort: dict = None,
    page: int = 1,
    limit: int = 100
):
    skip = (page - 1) * limit
    db_map = {
       
        "solforge_users": solforge_users,
        "coins": coins,
        "coinstatuses": coinstatuses,
        "scratchhistories": scratchhistories,
        "spinhistories": spinhistories
    }

    if collection not in db_map:
        return f"❌ Unknown collection: `{collection}`"

    try:
        cursor = db_map[collection].find(filter)
        if sort:
            cursor = cursor.sort(list(sort.items()))
        results = list(cursor.skip(skip).limit(limit))
        return results
    except Exception as e:
        return f"❌ Mongo query failed: {str(e)}"

def find_one_mongo(collection: str, filter: dict):
    db_map = {
        "solforge_users": solforge_users,
        "coins": coins,
        "coinstatuses": coinstatuses,
        "scratchhistories": scratchhistories,
        "spinhistories": spinhistories
    }

    if collection not in db_map:
        return f"❌ Unknown collection: `{collection}`"

    try:
        result = db_map[collection].find_one(filter)
        return result or f"❌ No result found with filter: {filter}"
    except Exception as e:
        return f"❌ Mongo find_one failed: {str(e)}"

def calculate_solforge_coin_volume(coin_name_or_ticker: str):
    # Step 1: Find the coin
    coin = coins.find_one({
        "$or": [
            { "name": { "$regex": coin_name_or_ticker, "$options": "i" } },
            { "ticker": { "$regex": coin_name_or_ticker, "$options": "i" } }
        ]
    })

    if not coin:
        return f"❌ Coin named '{coin_name_or_ticker}' not found."

    coin_id = coin["_id"]
    ticker = coin.get("ticker", "Unknown")
    name = coin.get("name", "Unknown")

    # Step 2: Fetch all statuses for this coin
    statuses = list(coinstatuses.find({ "coinId": coin_id }))

    total_lamports = 0
    trade_count = 0

    for status in statuses:
        for record in status.get("record", []):
            if record.get("holdingStatus") in [0, 1]:  # Buy or Sell
                amount = record.get("amount", 0)
                if isinstance(amount, str):
                    amount = int(float(amount))
                total_lamports += amount
                trade_count += 1

    # Convert to SOL and USD
    total_sol = total_lamports / 1_000_000_000
    sol_price = fetch_sol_price()
    volume_usd = total_sol * sol_price

    return (
        f"📊 Volume for **{name} (${ticker})**\n"
        f"• Trades: {trade_count}\n"
        f"• Volume: {total_sol:.2f} SOL\n"
        f"• Est. Value: ${volume_usd:,.2f}"
    )