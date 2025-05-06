from bson import ObjectId
from tools.db import coins, coinstatuses, solforge_users

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
    }

    if collection not in db_map:
        return f"❌ Unknown collection: `{collection}`"

    try:
        result = db_map[collection].find_one(filter)
        return result or f"❌ No result found with filter: {filter}"
    except Exception as e:
        return f"❌ Mongo find_one failed: {str(e)}"

def get_coin_info(name_or_ticker: str):
    # Case-insensitive match on name or ticker
    coin = coins.find_one({
        "$or": [
            { "name": { "$regex": f"^{name_or_ticker}$", "$options": "i" } },
            { "ticker": { "$regex": f"^{name_or_ticker}$", "$options": "i" } }
        ]
    })
    return coin if coin else f"❌ No coin found with name or ticker '{name_or_ticker}'"

def get_coinstatuses_for_coin(name_or_ticker: str):
    coin = get_coin_info(name_or_ticker)
    if not coin or isinstance(coin, str):
        return coin

    coin_id = coin["_id"]
    return list(coinstatuses.find({ "coinId": coin_id }).sort("time", -1).limit(100))