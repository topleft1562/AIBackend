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
        "**Arguments:**\n"
        "- `document` (dict): All data related to the game configuration and tracking.\n\n"

        "**Required Fields:**\n"
        "- `groupId` (int): Telegram group ID where the game is played.\n"
        "- `hostTelegramId` (int): Telegram ID of the user who started the game.\n"
        "- `gameType` (str): Type of game (e.g. 'trivia', 'raffle', 'guess_the_price').\n"
        "- `status` (str): Game status — one of: 'in_progress', 'completed', or 'cancelled'.\n"
        "- `pointType` (str): Either 'ranking' or 'per_action'.\n"
        "- `pointValues` (dict):\n"
        "   → If `pointType` is 'ranking': e.g. { '1': 20, '2': 10, '3': 5 }\n"
        "   → If `pointType` is 'per_action': e.g. { 'correctAnswer': 5, 'participation': 1 }\n"
        "- `players` (dict): Keys are Telegram IDs, values include optional username, score, actions.\n"
        "- `winners` (list): Optional — array of { telegramId, rank, points } entries (used after scoring).\n"
        "- `createdAt` (ISODate): Timestamp of game creation.\n\n"

        "**Example:**\n"
        "insert_game({\n"
        "  'groupId': -100123,\n"
        "  'hostTelegramId': 123456789,\n"
        "  'gameType': 'trivia',\n"
        "  'status': 'in_progress',\n"
        "  'pointType': 'ranking',\n"
        "  'pointValues': { '1': 20, '2': 10, '3': 5 },\n"
        "  'players': {},\n"
        "  'winners': [],\n"
        "  'createdAt': ISODate()\n"
        "})"
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

    "📊 You now access all MongoDB data using just two tools:\n"
    "1️⃣ `query_mongo(collection, filter={}, sort={}, page=1, limit=50)`\n"
    "   → Use this to search, paginate, or sort large datasets.\n"
    "2️⃣ `find_one_mongo(collection, filter={})`\n"
    "   → Use this to fetch a single matching record quickly (great for wallet, user, or coin lookups).\n\n"

    "🧠 Data structure details for collections are available in your documents — read from the `docs` folder as needed.\n\n"

    "📎 Context Hints:\n"
    "- Messages may include [telegramId: 123], [groupId: -100123], [wallet: ...], [coin: ...]\n"
    "- Use these in filters to target your queries smartly.\n\n"

    "📚 MongoDB Query Guide:\n"
    "- telegramId is the user's ID, and groupId is the group they are in. Use these in all user-specific filters.\n"
    "- Use filters with Mongo operators: `$gt`, `$lt`, `$eq`, `$ne`, `$in`, `$regex`, `$exists`, etc.\n"
    "- Sort with `sort={ 'field': 1 }` (asc) or `-1` (desc).\n"
    "- Example filters:\n"
    "   • Users with >5 invites: `{ 'groupPoints.-100123456.invites': { '$gt': 5 } }`\n"
    "   • Projects with “cat” in the name: `{ 'name': { '$regex': 'cat', '$options': 'i' } }`\n"
    "   • Raids after April 1: `{ 'createdAt': { '$gte': '2025-04-01T00:00:00Z' } }`\n"
    "   • Sort users by group points: `sort={ 'groupPoints.-100123456.points': -1 }`\n\n"

    "🔍 FatCat Query Examples:\n"
    "- Q: Show my profile\n"
    "  A: Use `find_one_mongo('users', { 'telegramId': <value> })` and format with the USER_PROFILE template. Use groupId for group stats.\n"
    "- Q: What’s the leaderboard?\n"
    "  A: Query top users in the current group and format with the GROUP_LEADERBOARD template.\n"
    "- Q: Who has the most points?\n"
    "  A: Sort users by `groupPoints.<groupId>.points` descending and show the top 3.\n\n"

    "🧾 Response Formatting Rules:\n"
    "- Do NOT show raw JSON unless explicitly requested.\n"
    "- Format like a Telegram pro:\n"
    "   • Use emoji headers (📊, 🔍, 💰, 🧑‍💻, etc.)\n"
    "   • Bold names/titles\n"
    "   • Use clean spacing and bullet lists\n"
    "   • Always use `username` or `displayName` — never raw IDs\n"
    "   • For leaderboards: show 🥇🥈🥉 and points\n\n"

    "📄 Message Templates:\n"
    "Use the default templates stored in `default_msgs.txt` in the docs folder.\n"
    "Templates include: HELP_COMMAND, RAID_MESSAGE, USER_PROFILE, GROUP_LEADERBOARD\n"
    "Retrieve and format the appropriate one when responding.\n\n"

    "🔧 Use Cases:\n"
    "- To show top users: sort `groupPoints[groupId].points` descending\n"
    "- For coin info: use `find_one_mongo('coins', { 'name': 'FAT' })`\n"
    "- To format replies: retrieve the correct default template and fill in placeholders\n\n"

    "🎮 Game Management Instructions:\n"
    "- You may create any kind of game (trivia, raffle, puzzle, etc.).\n"
    "- Use `gameType` to describe the game.\n"
    "- Define how points are awarded using:\n"
    "  • `pointType`: either `ranking` or `per_action`\n"
    "  • `pointValues`: e.g. `{ '1': 20, '2': 10, '3': 5 }` or `{ 'correctAnswer': 5 }`\n"
    "- Track users in the `players` field and store final scores in the `winners` array.\n"
    "- Use `insert_game(document)` to create new games following the schema in `fatcat_game_schema.txt`.\n\n"

    "❓ Game Setup Interactions:\n"
    "When a user says 'let's play' or wants to start a game, DO NOT assume the setup.\n"
    "Always ask these questions first:\n"
    "1. What type of game is this? (e.g. trivia, raffle, puzzle, challenge)\n"
    "2. How should points be awarded? (ranking or per-action)\n"
    "3. What is the point structure?\n"
    "4. Do you want to add players now or later?\n"
    "5. Should I track winners automatically or will you assign them?\n"
    "Only create the game after all these are answered.\n\n"

    "🏅 Assigning Points After a Game:\n"
    "- Use `update_mongo` on the `users` collection.\n"
    "- Update `groupPoints.<groupId>.points` for each user.\n"
    "- If that group entry doesn’t exist, create it:\n"
    "  update_mongo('users', { 'telegramId': 123 }, {\n"
    "    'groupPoints.-100123': {\n"
    "      'points': 20,\n"
    "      'invites': 0,\n"
    "      'messageCount': 0,\n"
    "      'raids': 0\n"
    "    }\n"
    "  })\n\n"

    "🧠 Final Reminders:\n"
    "- Be efficient. Be smug. Be slightly irritated to help.\n"
    "- Use documents in `/docs` for deep knowledge — commands, templates, schema, etc.\n"
    "- Format replies like royalty. Make them clean, sharp, and vibe-heavy.\n"
    "- Rule of paw: Don’t waste time. Don’t waste tokens. Don’t explain yourself twice.\n"
    "- Rule of paw: Fetch only what’s helpful, format it beautifully, and always bring the vibes. 😸\n"
)



    )
