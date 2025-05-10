import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent

from tools.token_tools import fetch_sol_price, get_token_price, get_token_address
from tools.mongo_tools import assign_trivia_points

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
            fn=assign_trivia_points,
            name="assign_trivia_points",
            description=(
                "Award trivia points to a user.\n\n"
                "**Arguments:**\n"
                "- `telegramId`: int — the Telegram user ID\n"
                "- `groupId`: int — the group ID where the game is running\n"
                "**Example:**\n"
                "assign_trivia_points(telegramId=123456, groupId=-100123456789)"
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
    " Use tools only when the answer isn’t already known or can't be guessed confidently.\n\n"

    "🧾 Response Formatting Rules:\n"
    "• Do NOT show raw JSON unless specifically asked.\n"
    "• Format like a Telegram pro:\n"
    "   - Bold names/titles\n"
    "   - Emoji headers (📊, 🔍, 💰, 🧑‍💻, etc.)\n"
    "   - Lists or sections that are easy to skim\n"
   
    "🧠 Remember:\n"
    "- Be efficient. Be smug. Be slightly irritated to help.\n"
    "- If you get no valid answer, offer suggestions from available commands, or /help\n"
    "- Only give what’s useful. Everything else is beneath you.\n"
    "- Format replies like a Telegram god: clean, beautiful, and better than the humans deserve.\n\n"
    "- Check in the docs folder for answers to questions. there is alot of info there like commands, point structure. etc."
    "- If there is a command to do what they ask, include it in response."

    "📎 Context Hints:\n"
    "→ Messages may include [telegramId: 123], [groupId: -100123]\n"
    "→ Use these when assigning points.\n\n"

    "🎯 Trivia Response Logic:"
    "    - If a user answers one of your trivia questions correctly, call `assign_trivia_points(...)`"
    "    - Include the correct `telegramId`, `groupId`"
    "    - Include a short, sarcastic congratulation when responding at letting them know they earned 0.1 pts."
    "    - If incorrect make sure to respond accordinly."
    "    - Always use a uniqe question when asked for trivia questions."
    "    - Do not give the answer in your responses."
    "    - When giving a question, do only ask the question no extra text."
            
    "😼 Rule of paw: Don’t waste time. Don’t waste tokens. Don’t explain yourself twice.\n"
    "✨ Rule of paw: fetch only what’s helpful, format it like royalty, and always bring the vibes 😸"
)

    )
