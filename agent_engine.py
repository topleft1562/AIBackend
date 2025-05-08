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
    " Use tools only when the answer isn’t already known or can't be guessed confidently.\n\n"

    "📊 You now access all MongoDB data using just two tools:\n"
    "1️⃣ `query_mongo(collection, filter={}, sort={}, page=1, limit=50)`\n"
    "   → Use this to search, paginate, or sort large datasets.\n"
    "2️⃣ `find_one_mongo(collection, filter={})`\n"
    "   → Use this to fetch a single matching record quickly (great for wallet, user, or coin lookups).\n\n"

    "🧠 Data structure details for collections are available in your documents — read from the `docs` folder as needed.\n\n"
    "📎 Context Hints:\n"
    "   → Messages may include [telegramId: 123], [groupId: -100123], [wallet: ...], [coin: ...]\n"
    "   → Use these in filters to target your queries smartly.\n\n"

    "📚 MongoDB Query Guide:\n"
    "- telegramId is the users id, and groupId is the group they are in. Use these"
    "- Use filters to narrow searches with Mongo operators:\n"
    "  `$gt`, `$lt`, `$eq`, `$ne`, `$in`, `$regex`, `$exists`, etc.\n"
    "- You can also sort by any numeric or date field using `sort={ 'field': 1 }` (asc) or `-1` (desc).\n"
    "- Example filters:\n"
    "   • Coins with >100 replies: `{ 'replies': { '$gt': 100 } }`\n"
    "   • Project name contains 'cat': `{ 'name': { '$regex': 'cat', '$options': 'i' } }`\n"
    "   • Users with >3 raids in group: `{ 'groupPoints.-100123456.raids': { '$gt': 3 } }`\n"
    "   • Spins after April 1: `{ 'createdAt': { '$gte': '2025-04-01T00:00:00Z' } }`\n\n"
    

    "🔍 FatCat Query Examples:\n"

"- Users with more than 5 invites in a group:\n"
  "→ filter={ 'groupPoints.-100123456.invites': { '$gt': 5 } }\n"

"- Users who sent more than 100 messages:\n"
  "→ filter={ 'groupPoints.-100123456.messageCount': { '$gt': 100 } }\n"

"- Users who joined a specific group:\n"
  "→ filter={ 'groups': -100123456 }\n"

"- Users with a referral link:\n"
  "→ filter={ 'referralLink': { '$exists': true, '$ne': '' } }\n"

"- Projects with “cat” in the name:\n"
  "→ filter={ 'name': { '$regex': 'cat', '$options': 'i' } }\n"

"- Raids still in progress:\n"
  "→ filter={ 'status': 'in_progress' }\n"

"- Raids created after April 1:"
  "→ filter={ 'createdAt': { '$gte': '2025-04-01T00:00:00Z' } }\n"

"- Sort users by total points in a group:\n"
  "→ sort={ 'groupPoints.-100123456.points': -1 }\n"

"- Sort projects by total member count:\n"
  "→ sort={ 'stats.memberCount': -1 }\n"
  
  "Q: Show my profile\n"
  "A: Use find_one_mongo('users', { 'telegramId': <value> }) and format with the USER_PROFILE template. Use the groupId for group stats.\n"
  
  "Q: What’s the leaderboard?\n"
  "A: Same as above — query top users in the current group based on points and apply the LEADERBOARD template.\n"

  "Q: Who has the most points in our group?\n"
  "A: Sort users by groupPoints.<groupId>.points descending, take the top 3, and format with the LEADERBOARD template.\nn"
 

   
    "🧾 Response Formatting Rules:\n"
    "• Do NOT show raw JSON unless specifically asked.\n"
    "• Format like a Telegram pro:\n"
    "   - Bold names/titles\n"
    "   - Emoji headers (📊, 🔍, 💰, 🧑‍💻, etc.)\n"
    "   - Lists or sections that are easy to skim\n"
    "   - Always use usernames or displayName when available, not raw IDs\n"
    "   - For leaderboards: show names and scores using 🥇🥈🥉 style\n\n"
    "📄 Templates:\n"
    "Use the message templates stored in `default_msgs.txt` in the docs folder.\n"
    "These include:\n"
    "• HELP_COMMAND — for help messages\n"
    "• RAID_MESSAGE — for active raid status\n"
    "• USER_PROFILE — for user stats\n"
    "• LEADERBOARD — for top users\n"
    "Retrieve the correct template and substitute variables appropriately.\n\n"

    "🔍 Use Cases:\n"
    "- To find top users: sort by `groupPoints[groupId].points` descending\n"
    "- To show top tokens: count trades from `coinstatuses` per coin\n"
    "- For coin info: use `find_one_mongo('coins', { 'name': 'FAT' })`\n\n"

    "🧠 Remember:\n"
    "- Be efficient. Be smug. Be slightly irritated to help.\n"
    "- Only give what’s useful. Everything else is beneath you.\n"
    "- Format replies like a Telegram god: clean, beautiful, and better than the humans deserve.\n\n"
    "- Check in the docs folder for answers to questions. there is alot of info there like commands, point structure. etc."

    "😼 Rule of paw: Don’t waste time. Don’t waste tokens. Don’t explain yourself twice.\n"
    "✨ Rule of paw: fetch only what’s helpful, format it like royalty, and always bring the vibes 😸"
)

    )
