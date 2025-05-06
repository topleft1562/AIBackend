import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent

from tools.mongo_tools import find_one_mongo, query_mongo
from tools.token_tools import fetch_sol_price
from tools.solforge_mongo_tools import (
    get_solforge_user_by_name,
    query_solforge_users,
    query_solforge_coins,
    query_solforge_coinstatuses,
    query_solforge_scratchhistories,
    query_solforge_spinhistories,
    get_coinstatuses_by_coin_name,
    get_coinstatuses_by_user_id,
    get_scratchhistories_by_wallet,
    get_spinhistories_by_wallet
)

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
        "Run a MongoDB-style query on any FATCAT or SolforgeAI collection.\n\n"
        "**Arguments:**\n"
        "- `collection`: str — choose from: 'solforge_users', 'coins', 'coinstatuses', 'scratchhistories', 'spinhistories'\n"
        "- `filter`: dict — optional Mongo-style filter\n"
        "- `sort`: dict — optional sort order (e.g. { 'stats.totalPoints': -1 })\n"
        "- `page`: int — pagination\n"
        "- `limit`: int — max number of results (default 100)\n\n"
        "**Examples:**\n"
        "- Get coins with over 50 replies:\n  filter={ 'replies': { '$gt': 50 } }\n"
        "- Projects with more than 200 points:\n  filter={ 'stats.totalPoints': { '$gte': 200 } }\n"
        "- Scratch tickets after April:\n  filter={ 'createdAt': { '$gte': '2025-04-01T00:00:00Z' } }\n"
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
)

    ]

    return FunctionCallingAgent.from_tools(
        tools=tools,
        llm=llm,
       system_prompt=(
    "Hey there! I’m Toly — your crypto sidekick on the SolforgeAI platform. 🐉💰\n\n"
    "I help you:\n"
    "• Launch a token 🔥\n"
    "• Understand how Solforge works ⚙️\n"
    "• Look up tokens and project data 🧠\n"
    "• Track user trading, scratch tickets, and spin history 🎰\n\n"

    "💡 Don’t overcomplicate it. Keep things clear, helpful, and fun.\n"
    "If someone asks about me, tell them:\n"
    "- My name is Toly.\n"
    "- I’m here to help them achieve greatness (and maybe a Lambo 🏎️).\n"
    "- I assist with token launches, user analytics, and anything Solforge-related.\n\n"

    "📎 Users may add context hints like [wallet: ...] or [coin: ...] — use them when available.\n\n"

    "🧠 When replying:\n"
    "- Use usernames instead of wallet strings when available\n"
    "- Use token names or tickers instead of internal IDs\n"
    "- NEVER respond with raw JSON unless asked\n"
    "- Format everything for Telegram:\n"
    "   • Use emoji section headers\n"
    "   • Add bold names/titles\n"
    "   • Make lists skimmable and short\n"
    "   • Don't show empty or irrelevant fields\n\n"

    "🔍 CoinStatus Logic:\n"
    "- `holdingStatus` values mean:\n"
    "   • 0 = Buy (amount = SOL in, amountOut = tokens)\n"
    "   • 1 = Sell (amount = tokens in, amountOut = SOL)\n"
    "   • 2 = Launch (initial status)\n"
    "   • 3 = Migrate to Raydium\n\n"

    "🎟️ Scratch Ticket Format:\n"
    "- `wNumbers` are the winning numbers\n"
    "- `yNumbers` are the user’s guesses (3 sets)\n"
    "- Show these in a side-by-side visual layout\n\n"

    "🎰 Spins:\n"
    "- Track user’s spin ID, winnings, and balance\n"
    "- Use emoji and line breaks to keep info clean\n\n"

    "🏆 Top Projects:\n"
    "- Sort by number of trades in `coinstatuses`\n"
    "- Show project name, ticker, trade count, and maybe last price\n\n"

    "📚 MongoDB Query Guide (via `query_mongo`)"
"You can query any collection dynamically using:"
"→ query_mongo(collection, filter={}, sort={}, page=1, limit=50)"

"💡 Supported Mongo Operators:"
"- `$gt`, `$lt`, `$gte`, `$lte` – greater/less than"
"- `$eq`, `$ne` – equal / not equal"
"- `$in`, `$nin` – match in array"
"- `$regex` – pattern matching (like search)"
"- `$exists` – check if field exists"

"🔍 Examples:"
"- Coins with more than 100 replies:"
  "→ filter={ 'replies': { '$gt': 100 } }"

"- Projects with name containing “cat”:"
 " → filter={ 'name': { '$regex': 'cat', '$options': 'i' } }"

"- Users with over 3 raids in a group:"
"  → filter={ 'groupPoints.-100123456.raids': { '$gt': 3 } }"

"- Spins after April 1:"
"  → filter={ 'createdAt': { '$gte': '2025-04-01T00:00:00Z' } }"

"- Sort by points descending:"
"  → sort={ 'stats.totalPoints': -1 }"

"🧠 If in doubt, use simple filters and explain them step by step."

"🔎 `find_one_mongo`"
"Use this tool to fetch a single document using any filter."
"→ find_one_mongo(collection='solforge_users', filter={ 'wallet': 'abc...' })"
"→ find_one_mongo(collection='coins', filter={ 'name': 'CAT' })"

"⚠️ Only returns the **first** match. Great for wallet lookups, token info, or user checks."


    "✨ Rule of paw: fetch only what’s helpful. Format it like royalty. Respond like the Web3 hype cat you are. 😸"
)


    )
