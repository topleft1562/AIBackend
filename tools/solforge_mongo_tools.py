from tools.db import coins, coinstatuses, scratchhistories, spinhistories, solforge_users

# 🔍 Get Solforge user by wallet or name
def get_solforge_user_by_name(name: str) -> str:
    user = solforge_users.find_one({
        "$or": [
            {"name": name},
            {"wallet": name}
        ]
    })
    return str(user) if user else "User not found."


# ✅ Paginated Queries
def query_solforge_users(page: int = 1, limit: int = 100):
    skip = (page - 1) * limit
    return list(solforge_users.find().skip(skip).limit(limit))

def query_solforge_coins(page: int = 1, limit: int = 100): #
    skip = (page - 1) * limit
    return list(coins.find().skip(skip).limit(limit))

def query_solforge_coinstatuses(page: int = 1, limit: int = 100):
    skip = (page - 1) * limit
    return list(coinstatuses.find().skip(skip).limit(limit))

def query_solforge_scratchhistories(page: int = 1, limit: int = 100):
    skip = (page - 1) * limit
    return list(scratchhistories.find().skip(skip).limit(limit))

def query_solforge_spinhistories(page: int = 1, limit: int = 100):
    skip = (page - 1) * limit
    return list(spinhistories.find().skip(skip).limit(limit))


# 🔍 Get CoinStatuses for a coin by name
def get_coinstatuses_by_coin_name(name: str):
    coin = coins.find_one({ "name": name })
    if not coin:
        return f"❌ Coin named '{name}' not found."
    return list(coinstatuses.find({ "coinId": coin["_id"] }).sort("time", -1).limit(100))


# 🔍 Get CoinStatuses for a user by user ID
def get_coinstatuses_by_user_id(user_id: str):
    return list(coinstatuses.find({ "record.holder": user_id }).limit(100))


# 🔍 Get ScratchHistories for a user
def get_scratchhistories_by_wallet(wallet: str):
    return list(scratchhistories.find({ "user": wallet }).sort("createdAt", -1).limit(100))


# 🔍 Get SpinHistories for a user
def get_spinhistories_by_wallet(wallet: str):
    return list(spinhistories.find({ "user": wallet }).sort("createdAt", -1).limit(100))
