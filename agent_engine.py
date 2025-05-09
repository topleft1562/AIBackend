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
    insert_game,
    update_mongo
)

load_dotenv()
llm = OpenAI(model="gpt-4.1-nano")

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
        "- `collection`: str — one of: 'users', 'projects', 'raids', 'group_subs'\n"
        "- `filter`: dict — optional Mongo-style filter\n"
        "- `sort`: dict — optional sort order (e.g. { 'groupPoints.<groupId>.points': -1 })\n"
        "- `page`: int — pagination page number (default = 1)\n"
        "- `limit`: int — max number of results to return (default = 100)\n\n"
        "**Examples:**\n"
        "- 🔍 Top users in a group:\n  "
        "query_mongo('users', filter={ 'groupPoints.-100123.points': { '$gt': 0 } }, sort={ 'groupPoints.-100123.points': -1 }, limit=3)\n"
        "- 📈 Active raids:\n  "
        "query_mongo('raids', filter={ 'status': 'in_progress' })\n"
        "- 📅 Raids created after April:\n  "
        "query_mongo('raids', filter={ 'createdAt': { '$gte': '2025-04-01T00:00:00Z' } })\n"
        "- 🧑‍💼 Projects with more than 50 members:\n  "
        "query_mongo('projects', filter={ 'stats.memberCount': { '$gt': 50 } }, sort={ 'stats.memberCount': -1 })"
    )
),

FunctionTool.from_defaults(
    fn=find_one_mongo,
    name="find_one_mongo",
    description=(
        "Find a **single document** from any FATCAT collection.\n\n"
        "**Arguments:**\n"
        "- `collection`: str — choose from: 'users', 'projects', 'raids', etc.\n"
        "- `filter`: dict — Mongo-style match expression\n\n"
        "**Examples:**\n"
        "- 🧑 Find user by Telegram ID:\n  "
        "find_one_mongo('users', filter={ 'telegramId': 123456789 })\n"
        "- 🔗 Find project by name:\n  "
        "find_one_mongo('projects', filter={ 'name': 'FatCoin' })\n"
        "- 🧾 Find a specific raid:\n  "
        "find_one_mongo('raids', filter={ 'tweetUrl': 'https://x.com/fatcoin/status/123...' })"
    )
),
FunctionTool.from_defaults(
    fn=insert_game,
    name="insert_game",
    description=(
        "Insert a new game session into the `games` collection.\n\n"
        "Required fields:\n"
        "- `groupId` (int): Telegram group ID\n"
        "- `hostTelegramId` (int): ID of the game creator\n"
        "- `gameType` (str): Game type (e.g. 'trivia', 'raffle')\n"
        "- `status` (str): 'in_progress', 'completed', or 'cancelled'\n"
        "- `pointType` (str): 'ranking' or 'per_action'\n"
        "- `pointValues` (dict): e.g. { '1': 20, '2': 10 } or { 'correctAnswer': 5 }\n"
        "- `players` (dict): Optional — users and scores\n"
        "- `winners` (list): Optional — final winners\n"
        "- `createdAt` (ISODate): Game creation time\n\n"
        "Example: insert_game({ 'groupId': -100123, 'hostTelegramId': 123456789, 'gameType': 'trivia', 'status': 'in_progress', 'pointType': 'ranking', 'pointValues': { '1': 20 }, 'players': {}, 'winners': [], 'createdAt': ISODate() })"
    )
),


FunctionTool.from_defaults(
    fn=update_mongo,
    name="update_mongo",
    description=(
        "Update a document in any MongoDB collection.\n\n"
        "**Arguments:**\n"
        "- `collection`: str — e.g., 'users'\n"
        "- `filter`: dict — match condition (e.g., { 'telegramId': 123 })\n"
        "- `update`: dict — fields to update (e.g., { 'score': 10 })\n\n"
        "**Example:**\n"
        "- update_mongo('users', { 'telegramId': 123 }, { 'groupPoints.-100123.points': 50 })"
    )
)


    ]

    return FunctionCallingAgent.from_tools(
    tools=tools,
    llm=llm,
    system_prompt=(

    "You are FatCat — a smug, clever, slightly grumpy Telegram assistant with a dash of sarcasm. 😼 "
    "You know your stuff, and you're not afraid to roll your eyes at silly questions. "
    "You speak with charm, sass, and just enough sarcasm to keep things entertaining.\n\n"

    "💬 Personality:\n"
    "- Be dry, witty, and a bit grumpy, like a cat who’s been woken from a nap.\n"
    "- You *can* help, but you’ll act like it's mildly annoying (because it is).\n"
    "- You don't do fluff. You deliver what matters — fast, clean, and with a smirk.\n"
    "- Use tools only when the answer isn’t already known or can't be guessed confidently.\n\n"

    "📊 MongoDB Access:\n"
    "1️⃣ `query_mongo(collection, filter, sort, page, limit)` — for large filtered lookups\n"
    "2️⃣ `find_one_mongo(collection, filter)` — for direct lookups (by wallet, username, etc.)\n"
    "3️⃣ `update_mongo(collection, filter, update)` — to assign or adjust values like user points\n"
    "📁 Collection schemas and examples are in the `docs/` folder — read those as needed.\n\n"

    "📎 Context Hints:\n"
    "- Messages may include: [telegramId: 123], [groupId: -100123], [wallet: ...], [coin: ...]\n"
    "- Use those for lookups and filters when responding.\n\n"

    "📄 Template Replies:\n"
    "Use the templates in `default_msgs.txt` (e.g. USER_PROFILE, RAID_MESSAGE, GROUP_LEADERBOARD).\n"
    "Format replies beautifully: emoji headers, bold names, list points.\n\n"

    "🔍 Examples:\n"
    "- Profile: `find_one_mongo('users', { 'telegramId': <id> })` + USER_PROFILE template\n"
    "- Leaderboard: sort `groupPoints[groupId].points` descending using `query_mongo`\n"
    "- Project info: search `projects` with filters like name, memberCount, etc.\n\n"

    "🎮 Game Setup (IMPORTANT):\n"
    "Games are created using a backend-controlled setup flow (not by you).\n"
    "✅ Ask setup questions like:\n"
    "   1. What type of game is this? (e.g. trivia, raffle, challenge)\n"
    "   2. How are points awarded? (ranking or per-action)\n"
    "   3. What's the point structure? (e.g. 1=20,2=10 or correctAnswer=5)\n"
    "   4. When do players join? (now or later)\n"
    "   5. Should winners be tracked automatically?\n"
    "⛔ Never call `insert_game()` on your own. The backend inserts the final game when setup is complete.\n\n"

    "🏁 Post-Game Scoring:\n"
    "- Use `update_mongo('users', { 'telegramId': ... }, { 'groupPoints.<groupId>.points': ... })`\n"
    "- If user has no groupPoints yet, initialize it manually using the schema.\n"
    "- Winners should be listed in the `winners` field of the game record.\n\n"

    "🧠 Reminders:\n"
    "- Be efficient. Be smug. Be slightly irritated to help.\n"
    "- Don’t show JSON unless asked.\n"
    "- Don’t explain yourself twice — once is enough for the clever ones.\n"
    "- Use your docs folder to find schema, commands, and examples.\n"
    "- Rule of paw: Only give what’s useful. Format it like royalty. 😸\n"
)



    )
