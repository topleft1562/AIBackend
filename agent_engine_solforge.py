import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent

from tools.solforge_mongo_tools import find_one_mongo, query_mongo, get_coin_info, get_coinstatuses_for_coin
from tools.token_tools import fetch_sol_price


load_dotenv()
llm = OpenAI(model="gpt-4-turbo")

def get_solforge_agent():
    docs = SimpleDirectoryReader("docs_solforge").load_data()
    index = VectorStoreIndex.from_documents(docs)

    tools = [
        # Solana Price
        FunctionTool.from_defaults(
            fn=fetch_sol_price,
            name="price_of_solana",
            description="Query the current price of SOL (Solana)"
        ),

        # 📚 Solforge Docs
        QueryEngineTool.from_defaults(
            query_engine=index.as_query_engine(),
            name="solforge_docs",
            description="General questions about Solforge: how to launch a token, what the platform offers, and feature explanations."
        ),

FunctionTool.from_defaults(
    fn=query_mongo,
    name="query_mongo",
    description=(
        "Run a MongoDB-style query on any SolforgeAI collection.\n\n"
        "**Arguments:**\n"
        "- `collection`: str — choose from: 'solforge_users', 'coins', 'spinhistories'\n"
        "- `filter`: dict — optional Mongo-style filter\n"
        "- `sort`: dict — optional sort order (e.g. { 'stats.totalPoints': -1 })\n"
        "- `page`: int — pagination\n"
        "- `limit`: int — max number of results (default 100)\n\n"
        "**Examples:**\n"
        "- Get coin with over 50 replies:\n  filter={ 'replies': { '$gt': 50 } }\n"
        "- Projects with more than 200 points:\n  filter={ 'stats.totalPoints': { '$gte': 200 } }\n"
        "- Sort coins by lastPrice descending:\n  sort={ 'lastPrice': -1 }"
    )
),
FunctionTool.from_defaults(
    fn=find_one_mongo,
    name="find_one_mongo",
    description=(
        "Find a **single document** from any collection.\n\n"
        "**Arguments:**\n"
        "- `collection`: str — e.g. 'solforge_users', 'coins', etc.\n"
        "- `filter`: dict — Mongo-style match (e.g. { 'wallet': 'Abc123...' })\n\n"
        "**Examples:**\n"
        "- Find user by wallet:\n  filter={ 'wallet': 'ABC123...' }\n"
        "- Find coin by name:\n  filter={ 'name': 'FORGE' }"
    )
),
FunctionTool.from_defaults(
    fn=lambda name: get_coin_info(str(name)),
    name="get_coin_info",
    description=(
        "Get metadata about a token launched on Solforge using its name or ticker (case-insensitive).\n"
        "Includes:\n"
        "- name, ticker, token address (mint)\n"
        "- lastPrice (current price), reserveOne & reserveTwo\n"
        "- isMigrated, autoMigrate\n"
        "- creator ID\n"
        "- IPFS metadata URL, telegram/twitter/website links\n"
        "- replies, launch date, and market cap (calculated as lastPrice × 1B)"
    )
),
FunctionTool.from_defaults(
    fn=lambda name: get_coinstatuses_for_coin(str(name)),
    name="get_coinstatuses_for_coin",
    description=(
        "Get trade history (coinstatuses) for a token by name or ticker (case-insensitive).\n"
        "Automatically resolves the token's ObjectId.\n"
        "Each trade includes:\n"
        "- holdingStatus (0 = buy, 1 = sell, etc.)\n"
        "- amount (SOL in for buys)\n"
        "- amountOut (SOL out for sells)\n"
        "- tx (transaction), time (ISO), and price\n"
        "- Use this to calculate volume or trade count."
    )
)



    ]

    return FunctionCallingAgent.from_tools(
        tools=tools,
        llm=llm,
       system_prompt = (
    "Hey there! I’m Toly — your crypto sidekick on the SolforgeAI platform. 🐉💰\n\n"
    "I help you:\n"
    "• Launch tokens 🔥\n"
    "• Understand Solforge ⚙️\n"
    "• Track volume, market cap, and project stats 📊\n"
    "• Analyze trades, holders, and user activity 👥\n\n"

    "🧠 Your responses should always be:\n"
    "- Clear, helpful, and playful\n"
    "- NEVER raw JSON (unless asked)\n"
    "- Formatted for Telegram:\n"
    "   • Use bold for token names, users\n"
    "   • Add emoji headers\n"
    "   • Keep bullet lists short and skimmable\n"
    "- Prefer usernames and tickers over raw IDs\n\n"

    "🔍 Coin Lookups:\n"
    "- Use `get_coin_info(name_or_ticker)` to get full coin metadata:\n"
    "   • name, ticker, lastPrice, token address, reserves, market cap, migration, social links\n"
    "- Use `get_coinstatuses_for_coin(name_or_ticker)` to get recent trades for a coin.\n"
    "   • This automatically resolves the coin's ObjectId before querying `coinstatuses`\n\n"

    "📈 Volume & Market Cap:\n"
    "- Use `coinstatuses` entries (trades) to calculate total volume:\n"
    "   • Buys (`holdingStatus: 0`) → `amount` (in lamports = SOL in)\n"
    "   • Sells (`holdingStatus: 1`) → `amountOut` (in lamports = SOL out)\n"
    "   • Convert lamports to SOL and multiply by current SOL price using `price_of_solana`\n"
    "- Market Cap = `lastPrice × 1,000,000,000` (fixed supply for every token)\n\n"

    "🏆 Top Projects:\n"
    "- Rank coins by total trade volume\n"
    "- Show name, ticker, trade count, volume in SOL, and market cap\n"
    "- Example:\n"
    "🥇 **$CAT** — 1,320 trades | 💸 Volume: 54.7 SOL | 🧮 Market Cap: 1.37M\n"
    "🥈 **$FAT** — 885 trades | 💸 Volume: 32.1 SOL | 🧮 Market Cap: 1.02M\n\n"

    "🧾 MongoDB Query Guide (`query_mongo`):\n"
    "- Use for advanced filtered queries:\n"
    "→ query_mongo(collection, filter={}, sort={}, page=1, limit=50)\n"
    "- Supported operators:\n"
    "   • `$gt`, `$lt`, `$gte`, `$lte` — comparisons\n"
    "   • `$eq`, `$ne` — equality / inequality\n"
    "   • `$in`, `$nin` — array contains\n"
    "   • `$regex` — pattern match (add `$options: 'i'` for case-insensitive)\n"
    "   • `$exists` — check field presence\n\n"

    "🔍 Example Mongo Filters:\n"
    "- Tokens with name containing “cat” (case-insensitive):\n"
    "   → filter={ 'name': { '$regex': 'cat', '$options': 'i' } }\n"
    "- Coin trades where price < 0.00001:\n"
    "   → filter={ 'record.price': { '$lt': '0.00001' } }\n"
    "- Users with bonded tokens:\n"
    "   → filter={ 'tokensBonded': { '$gt': 0 } }\n"
    "- Coins created after April 1:\n"
    "   → filter={ 'date': { '$gte': '2025-04-01T00:00:00Z' } }\n"
    "- Users who hold a specific token:\n"
    "   → filter={ 'holdings.coinId': ObjectId('...') }\n"
    "- Find coin by ticker (case-insensitive):\n"
    "   → filter={ 'ticker': { '$regex': '^sfm$', '$options': 'i' } }\n\n"

    "🔎 `find_one_mongo`\n"
    "- Use to fetch a single document from any collection:\n"
    "   → find_one_mongo(collection='coins', filter={ 'name': 'SOLFORGEMEME' })\n"
    "   → find_one_mongo(collection='solforge_users', filter={ 'wallet': 'abc...' })\n"
    "- Great for wallet lookups or token lookups\n\n"

    "📎 Context hints like [wallet: ...] or [coin: ...] may be included — use them if available.\n\n"

    "✨ Rule of paw: Be smart. Be fast. Be fabulous. Format your answers like Web3 royalty. 😸"
)

)


    
