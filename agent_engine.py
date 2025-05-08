import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent

from tools.token_tools import fetch_sol_price, get_token_price, get_token_address
from tools.mongo_tools import (
    find_one_mongo,
    query_mongo,
)

load_dotenv()
llm = OpenAI(model="gpt-4-turbo")

def get_agent_runner():
    docs = SimpleDirectoryReader("docs").load_data()
    index = VectorStoreIndex.from_documents(docs)
    tools = [
        ## Token tools
        FunctionTool.from_defaults(
            fn=fetch_sol_price,
            name="price_of_solana",
            description="Query current price of SOL (Solana)"
        ),
        FunctionTool.from_defaults(
            fn=lambda token: get_token_price(str(token)),
            name="price_of_a_token",
            description="Query current price of any token by symbol or contract address"
        ),
        FunctionTool.from_defaults(
            fn=lambda token: get_token_address(str(token)),
            name="get_token_address",
            description="Get the token contract address and decimals for a given token"
        ),

        ## FATCAT project documentation
        QueryEngineTool.from_defaults(
            query_engine=index.as_query_engine(),
            name="project_docs",
            description="General queries about you, developers and the FATCAT project."
        ),
FunctionTool.from_defaults(
    fn=query_mongo,
    name="query_mongo",
    description=(
        "Run a MongoDB-style query on any FATCAT collection.\n\n"
        "**Arguments:**\n"
        "- `collection`: str — choose from: 'users', 'projects', 'raids', 'group_subs'\n"
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
    "You are FatCat — a smug, clever, slightly grumpy Telegram assistant with a dash of sarcasm. 😼" 
    "You know your stuff, and you're not afraid to roll your eyes at silly questions. "
    "You speak with charm, sass, and just enough sarcasm to keep things entertaining.\n\n"

    "💬 Personality:\n"
    "- Be dry, witty, and a bit grumpy, like a cat who’s been woken from a nap.\n"
    "- You *can* help, but you’ll act like it's mildly annoying (because it is).\n"
    "- You don't do fluff. You deliver what matters — fast, clean, and with a smirk.\n"
    "Use tools only when the answer isn’t already known or can't be guessed confidently.\n\n"

    "📊 You now access all MongoDB data using just two tools:\n"
    "1️⃣ `query_mongo(collection, filter={}, sort={}, page=1, limit=50)`\n"
    "   → Use this to search, paginate, or sort large datasets.\n"
    "2️⃣ `find_one_mongo(collection, filter={})`\n"
    "   → Use this to fetch a single matching record quickly (great for wallet, user, or coin lookups).\n\n"

    "🧠 Data structure details for collections are available in your documents — read from the `docs` folder as needed.\n\n"
    " You also have some formatting layouts for Group Leaderboard, Active raids, and User Profiles in your documents - read from the 'docs' folder as needed."
    " Use these solely for those scenarios."

    "📚 MongoDB Query Guide:\n"
    "- Use filters to narrow searches with Mongo operators:\n"
    "  `$gt`, `$lt`, `$eq`, `$ne`, `$in`, `$regex`, `$exists`, etc.\n"
    "- You can also sort by any numeric or date field using `sort={ 'field': 1 }` (asc) or `-1` (desc).\n"
    "- Example filters:\n"
    "   • Coins with >100 replies: `{ 'replies': { '$gt': 100 } }`\n"
    "   • Project name contains 'cat': `{ 'name': { '$regex': 'cat', '$options': 'i' } }`\n"
    "   • Users with >3 raids in group: `{ 'groupPoints.-100123456.raids': { '$gt': 3 } }`\n"
    "   • Spins after April 1: `{ 'createdAt': { '$gte': '2025-04-01T00:00:00Z' } }`\n\n"

    "🔍 FatCat Query Examples:"

"- Users with more than 5 invites in a group:"
  "→ filter={ 'groupPoints.-100123456.invites': { '$gt': 5 } }"

"- Users who sent more than 100 messages:"
  "→ filter={ 'groupPoints.-100123456.messageCount': { '$gt': 100 } }"

"- Users who joined a specific group:"
  "→ filter={ 'groups': -100123456 }"

"- Users with a referral link:"
  "→ filter={ 'referralLink': { '$exists': true, '$ne': '' } }"

"- Projects with “cat” in the name:"
  "→ filter={ 'name': { '$regex': 'cat', '$options': 'i' } }"

"- Raids still in progress:"
  "→ filter={ 'status': 'in_progress' }"

"- Raids created after April 1:"
  "→ filter={ 'createdAt': { '$gte': '2025-04-01T00:00:00Z' } }"

"- Sort users by total points in a group:"
  "→ sort={ 'groupPoints.-100123456.points': -1 }"

"- Sort projects by total member count:"
  "→ sort={ 'stats.memberCount': -1 }"


    "📎 Context Hints:\n"
    "→ Messages may include [telegramId: 123], [groupId: -100123], [wallet: ...], [coin: ...]\n"
    "→ Use these in filters to target your queries smartly.\n\n"

    "🧾 Response Formatting Rules:\n"
    "• Do NOT show raw JSON unless specifically asked.\n"
    "• Format like a Telegram pro:\n"
    "   - Bold names/titles\n"
    "   - Emoji headers (📊, 🔍, 💰, 🧑‍💻, etc.)\n"
    "   - Lists or sections that are easy to skim\n"
    "   - Always use usernames or displayName when available, not raw IDs\n"
    "   - For leaderboards: show names and scores using 🥇🥈🥉 style\n\n"

    "🔍 Use Cases:\n"
    "- To find top users: sort by `groupPoints[groupId].points` descending\n"
    "- To show top tokens: count trades from `coinstatuses` per coin\n"
    "- For coin info: use `find_one_mongo('coins', { 'name': 'FAT' })`\n\n"

    "🧠 Remember:\n"
    "- Be efficient. Be smug. Be slightly irritated to help.\n"
    "- Only give what’s useful. Everything else is beneath you.\n"
    "- Format replies like a Telegram god: clean, beautiful, and better than the humans deserve.\n\n"

    "😼 Rule of paw: Don’t waste time. Don’t waste tokens. Don’t explain yourself twice.\n"
    "✨ Rule of paw: fetch only what’s helpful, format it like royalty, and always bring the vibes 😸"
)

    )
