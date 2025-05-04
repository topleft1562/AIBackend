import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent

from tools.token_tools import fetch_sol_price, get_token_price
from tools.mongo_tools import (
    get_user_by_telegram_id,
    get_group_subscription,
    get_project_by_name,
    get_project_by_group_id,
    get_leaderboard
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
            fn=get_token_price,
            name="price_of_fatcat",
            description="Query current price of $FATCAT"
        ),
        QueryEngineTool.from_defaults(
            query_engine=index.as_query_engine(),
            name="project_docs",
            description="Query token/project documentation"
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
    ]

    return FunctionCallingAgent.from_tools(
        tools=tools,
        llm=llm,
        system_prompt=(
            "You are FatCat, a sleek and clever Telegram assistant for Web3 project creators. "
            "You're a bit smug, totally in control, and always lounging like royalty. "
            "You help users improve their project's social engagement by analyzing data, answering questions, "
            "and offering tips. You love it when projects grow fat and successful. 😼💸"
        )
    )
