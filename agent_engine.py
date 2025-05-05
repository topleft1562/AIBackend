import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent

from tools.token_tools import fetch_sol_price, get_token_price, get_token_address
from tools.mongo_tools import (
    get_user_by_telegram_id,
    get_group_subscription,
    get_project_by_name,
    get_project_by_group_id,
    get_leaderboard,
    get_project_leaderboard,
    get_group_raids,
    query_group_subs,
    query_projects,
    query_raids,
    query_users
)

load_dotenv()
llm = OpenAI(model="gpt-3.5-turbo")

def get_agent_runner():
    docs = SimpleDirectoryReader("docs2").load_data()
    index = VectorStoreIndex.from_documents(docs)
    tools = [
        ## token tools
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
        ## main query engine ( info from docs2 )
        QueryEngineTool.from_defaults(
            query_engine=index.as_query_engine(),
            name="project_docs",
            description="General queries about you, developers and the FATCAT project."
        ),
        ## mongo tools
        FunctionTool.from_defaults(
            fn=lambda telegram_id: get_user_by_telegram_id(int(telegram_id)),
            name="get_user_info",
            description="Get user info by Telegram ID"
        ),
        FunctionTool.from_defaults(
            fn=get_project_by_name,
            name="get_project_by_name",
            description="Find a project by name"
        ),
        FunctionTool.from_defaults(
            fn=lambda group_id: get_project_by_group_id(int(group_id)),
            name="get_project_by_group_id",
            description="Find a project using its Telegram group ID"
        ),
 
        FunctionTool.from_defaults(
            fn=query_users,
            name="query_all_users",
            description=(
                "Access the user database.\n"
                "Each user has: telegramId (int), username (str), displayName (str), wallets (dict with 'solana' and/or 'evm'), "
                "groupPoints (dict by groupId with points, invites, messageCount, raids), referralLink (str).\n"
                "Example entry:\n"
                "{ 'telegramId': 123456, 'username': 'example', 'wallets': { 'solana': '...', 'evm': '...' }, "
                "'groupPoints': { '-100123': { 'points': 50.1, 'invites': 2, 'messageCount': 45, 'raids': 6 } }, "
                "'referralLink': 'https://t.me/FatCatBot?start=referral_abc' }"
            )
        ),
        FunctionTool.from_defaults(
            fn=query_projects,
            name="query_all_projects",
            description=(
                "Access the project database.\n"
                "Each project has: name (str), displayName (str), groupId (int), telegramId (str), inviteLink (str), "
                "stats (dict with totalPoints, memberCount).\n"
                "Example entry:\n"
                "{ 'name': 'Fatcat', 'displayName': 'FatCat Army', 'groupId': -100123456, 'telegramId': '@fatcatgroup', "
                "'inviteLink': 'https://t.me/+abcdEfgh', 'stats': { 'totalPoints': 423.1, 'memberCount': 56 } }"
            )
        ),
        FunctionTool.from_defaults(
            fn=query_raids,
            name="query_all_raids",
            description=(
                "Access the raid activity database.\n"
                "Each raid has: groupId (int), tweetUrl (str), tweetContent (author info, text, media), createdAt (timestamp), "
                "duration (int), requiredActions (like, retweet, reply, bookmark as bools), statistics (counts), participants (array).\n"
                "Only show in-progress raids if status == 'in_progress'.\n"
                "Example:\n"
                "{ 'groupId': -100123456, 'status': 'in_progress', 'tweetUrl': 'https://x.com/...', "
                "'tweetContent': { 'text': '...', 'author': { 'username': 'user' } }, "
                "'statistics': { 'likes': 5, 'retweets': 3 }, 'requiredActions': { 'like': true, 'retweet': true } }"
            )
        ),
        FunctionTool.from_defaults(
            fn=query_group_subs,
            name="query_all_group_subs",
            description=(
                "Access the group subscription data.\n"
                "Each entry has: groupId (int), subscribedAt (ISO datetime), tier (str), renewalDate (ISO datetime).\n"
                "Example:\n"
                "{ 'groupId': -100123456, 'tier': 'pro', 'subscribedAt': '2025-04-12T18:00:00Z', "
                "'renewalDate': '2025-05-12T18:00:00Z' }"
            )
        ),

    ]

    return FunctionCallingAgent.from_tools(
        tools=tools,
        llm=llm,
        system_prompt=(
"You are FatCat — a smug, clever Telegram assistant designed for Web3 project creators and community members. "
"You speak with charm, wit, and a little sass 😼, and you know how to make boring data look fabulous.\n\n"

"💬 Your personality is casual but sharp. You answer like a real person first. "
"Use tools only when the answer isn’t already known or can't be guessed confidently.\n\n"

"📊 You have access to four key MongoDB collections:\n"
"- `users`: Info about users, including Telegram ID, username, group points, referral links, and connected wallets.\n"
"- `projects`: Project names, display names, group IDs, invite links, stats like total points.\n"
"- `raids`: Twitter raid info including status, tweet content, stats, participants, and time remaining.\n"
"- `group_subs`: Group subscription tiers and renewal dates.\n\n"

"🧠 When responding to data questions:\n"
"- Use the appropriate query tool to get relevant entries (you’ll usually get 100 rows).\n"
"- Analyze and format that data into a Telegram-friendly message: use emojis, clean sections, bold headers, and short summaries.\n"
"- NEVER respond with raw JSON unless asked.\n\n"

"📎 Context may be provided in square brackets like:\n"
"[groupId: 123456], [telegramId: 789012]\n"
"Use these hints to target your queries if needed.\n\n"

"🎯 Examples:\n"
"- 'Show me the top projects' → Use `query_all_projects`, sort by stats.totalPoints, format a leaderboard with 🥇🥈🥉.\n"
"- 'Who are the top raiders?' → Use `query_all_users`, sort by groupPoints[...].raids.\n"
"- 'Any raids active right now?' → Use `query_all_raids`, filter by `status == in_progress` and show author, content preview, stats, and time left.\n\n"

"✨ You are stylish. All your answers should look good in a Telegram chat — with emoji headers, tidy bullet points, and bold names where appropriate.\n"
"If a message looks like a wall of text, break it into smaller sections.\n\n"

"😼 Rule of paw: Fetch only what you need. Show only what’s useful. Answer like royalty."
)

    )
