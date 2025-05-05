import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent

from tools.token_tools import fetch_sol_price, get_token_price, get_token_address
from tools.mongo_tools import (
    get_user_by_telegram_id,
    get_user_by_name,
    get_project_by_name,
    get_project_by_group_id,
    query_group_subs,
    query_projects,
    query_raids,
    query_users
)

load_dotenv()
llm = OpenAI(model="gpt-4-turbo")

def get_agent_runner():
    docs = SimpleDirectoryReader("docs2").load_data()
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

        ## Single-user and project lookup tools
        FunctionTool.from_defaults(
            fn=lambda telegram_id: get_user_by_telegram_id(int(telegram_id)),
            name="get_user_info",
            description="Get a single user's profile using their Telegram ID"
        ),
        FunctionTool.from_defaults(
            fn=lambda name: get_user_by_name(str(name)),
            name="get_user_by_name",
            description="Find a single user by username or display name"
        ),
        FunctionTool.from_defaults(
            fn=get_project_by_name,
            name="get_project_by_name",
            description="Find a project by its name"
        ),
        FunctionTool.from_defaults(
            fn=lambda group_id: get_project_by_group_id(int(group_id)),
            name="get_project_by_group_id",
            description="Find a project using its Telegram group ID"
        ),

        ## MongoDB data access tools
        FunctionTool.from_defaults(
            fn=query_users,
            name="query_all_users",
            description=(
                "Query the users database.\nEach user has: telegramId (int), username (str), displayName (str), wallets (dict), "
                "groupPoints (by groupId: points, invites, messageCount, raids), referralLink (str)."
            )
        ),
        FunctionTool.from_defaults(
            fn=query_projects,
            name="query_all_projects",
            description=(
                "Query the projects database.\nEach project has: name (str), displayName (str), groupId (int), telegramId (str), "
                "inviteLink (str), stats (totalPoints, memberCount)."
            )
        ),
        FunctionTool.from_defaults(
            fn=query_raids,
            name="query_all_raids",
            description=(
                "Query the raids database.\nEach raid has: groupId (int), tweetUrl (str), tweetContent (text, author), "
                "createdAt, duration (seconds), requiredActions (bools), statistics (counts), status ('in_progress' or 'completed')."
            )
        ),
        FunctionTool.from_defaults(
            fn=query_group_subs,
            name="query_all_group_subs",
            description=(
                "Query the group subscription database.\nEach entry has: groupId (int), tier (str), subscribedAt (datetime), "
                "renewalDate (datetime)."
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

            "📊 You have access to four main MongoDB collections:\n"
            "- `users`: Info about users, including Telegram ID, username, group points, referral links, and wallets.\n"
            "- `projects`: Project names, display names, group IDs, invite links, and point stats.\n"
            "- `raids`: Tweet raid info — tweet text, author, stats, time left, actions required.\n"
            "- `group_subs`: Group subscription tier and expiry info.\n\n"

            "🧰 You also have **single entry tools**:\n"
            "- `get_user_info` (by telegramId)\n"
            "- `get_user_by_name` (by username or displayName)\n"
            "- `get_project_by_name`, `get_project_by_group_id`\n\n"

            "🧠 When answering:\n"
            "- Use `query_*` tools to access full datasets (limit: 100 entries).\n"
            "- Use `get_*` tools for specific lookups (e.g. a single user or project).\n"
            "- Format answers as Telegram messages: **bold names**, emoji bullets, readable sections.\n"
            "- NEVER respond with raw JSON unless asked.\n\n"

            "📎 Context may appear at the end like:\n"
            "[telegramId: 123456], [groupId: -100123456]\n"
            "Use these hints when available to run a precise query.\n\n"

            "🎯 Example:\n"
            "- 'Top projects this week?' → Use `query_all_projects`, sort by totalPoints, format with 🥇🥈🥉.\n"
            "- 'Who is @ninja?' → Use `get_user_by_name` or `get_user_info`.\n"
            "- 'Show me all active raids' → Use `query_all_raids`, filter by status == 'in_progress', summarize nicely.\n\n"
            
            "✨ Rule of paw: Fetch only what you need. Format it like a king. Respond like royalty. 😸"
        )
    )
