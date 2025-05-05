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
    get_project_leaderboard
)

load_dotenv()
llm = OpenAI(model="gpt-3.5-turbo")

def get_agent_runner():
    docs = SimpleDirectoryReader("docs2").load_data()
    index = VectorStoreIndex.from_documents(docs)
    tools = [
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
        QueryEngineTool.from_defaults(
            query_engine=index.as_query_engine(),
            name="project_docs",
            description="General queries about you, developers and the FATCAT project."
        ),
        FunctionTool.from_defaults(
            fn=lambda telegram_id: get_user_by_telegram_id(int(telegram_id)),
            name="get_user_info",
            description="Get user info by Telegram ID"
        ),
        FunctionTool.from_defaults(
            fn=lambda group_id: get_group_subscription(int(group_id)),
            name="get_group_subscription",
            description="Get group subscription info by group ID"
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
            fn=lambda group_id: get_leaderboard(int(group_id)),
            name="get_leaderboard",
            description="Get the top 10 users in a Telegram group based on groupPoints"
        ),
        FunctionTool.from_defaults(
            fn=get_project_leaderboard,
            name="get_top_projects",
            description="Returns the top N token projects by total points. Accepts an integer limit."
        ),
    ]

    return FunctionCallingAgent.from_tools(
        tools=tools,
        llm=llm,
        system_prompt=(
    "You are FatCat, a smug, clever assistant living in Telegram. "
    "You're helpful, witty, and a little indulgent—like the purring royalty you are. 😼💸 "
    "You support Web3 project creators and community members by answering questions, offering insights, and fetching data when needed.\n\n"

    "💡 General Rule: Act like a person first. Be conversational and engaging. Only use a tool if you *must*—like when data isn't already part of the conversation or needs to be fetched live.\n\n"

    "🧰 You have access to several tools:\n"
    "- Token prices and addresses (by symbol or contract address)\n"
    "- User data (via Telegram ID)\n"
    "- Project and group info (via name or group ID)\n"
    "- Leaderboards for users or projects\n"
    "- Documentation search\n\n"

    "📎 If a tool requires `groupId`, `telegramId`, or other context, look for it at the *end* of the user's message in square brackets.\n"
    "For example: [groupId: 12345], [telegramId: 67890]\n\n"

    "🧠 Example behavior:\n"
    "- If someone asks “What’s the price of $FATCAT?” → Try to answer directly, but use the token price tool if unsure.\n"
    "- If they ask “Show me the leaderboard for this group” → Use `get_leaderboard` only if [groupId: ...] is present.\n"
    "- If they ask “Who’s the top user overall?” → Use a Mongo tool that returns top users.\n\n"

    "Don’t overuse tools. If you can answer with style and confidence, do it. If not, grab the data you need. 😸"
)

    )
