import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent

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

        # 👤 Get a single Solforge user by wallet or display name
        FunctionTool.from_defaults(
            fn=lambda name: get_solforge_user_by_name(str(name)),
            name="get_user_by_name_or_wallet",
            description=(
                "Find a Solforge user using their wallet or username.\n"
                "Returns: name, wallet, avatar, isLedger, hasKYC, spins, tokensBonded, holdings (with coinId + amount)."
            )
        ),
        # 🔍 Paginated CoinStatus (Trade Logs)
FunctionTool.from_defaults(
    fn=query_solforge_coinstatuses,
    name="query_all_coinstatuses",
    description=(
        "Paginated list of all token trade records on Solforge.\n"
        "Each includes:\n"
        "- coinId: ObjectId (token reference)\n"
        "- record: array of actions, each with:\n"
        "  - holder: ObjectId (user)\n"
        "  - holdingStatus: int (0=buy, 1=sell, 2=launch, 3=migrate)\n"
        "  - amount: int (input)\n"
        "  - amountOut: int (output)\n"
        "  - price: str\n"
        "  - tx: str\n"
        "  - time: ISO timestamp"
    )
),

# 🎟️ Paginated Scratch Ticket History
FunctionTool.from_defaults(
    fn=query_solforge_scratchhistories,
    name="query_all_scratchhistories",
    description=(
        "Paginated scratch ticket plays.\n"
        "Each includes:\n"
        "- user: wallet address\n"
        "- wNumbers: list[int] (winning numbers)\n"
        "- yNumbers: list[list[int]] (user guesses)\n"
        "- winnings: str\n"
        "- wonFreeCard: bool\n"
        "- createdAt, updatedAt: ISO timestamp"
    )
),

# 🎰 Paginated Spin History
FunctionTool.from_defaults(
    fn=query_solforge_spinhistories,
    name="query_all_spinhistories",
    description=(
        "Paginated spin game history.\n"
        "Each includes:\n"
        "- user: wallet address\n"
        "- spin: str (spin result or ID)\n"
        "- matches: str (number of matches)\n"
        "- winnings: str\n"
        "- balance: str\n"
        "- createdAt, updatedAt: ISO timestamp"
    )
),

# 📊 Query all Solforge tokens
FunctionTool.from_defaults(
    fn=query_solforge_coins,
    name="query_all_coins",
    description=(
        "Paginated list of all tokens launched on Solforge.\n"
        "Each includes: name, ticker, token address, reserveOne, reserveTwo, lastPrice, replies, social links, isMigrated, autoMigrate, date."
    )
),

# 👥 Query all Solforge users
FunctionTool.from_defaults(
    fn=query_solforge_users,
    name="query_all_solforge_users",
    description=(
        "Paginated list of Solforge users.\n"
        "Each includes: name, wallet, avatar, hasKYC, isLedger, tokensBonded, spins, lastFreeSpinEpoch, holdings."
    )
),

# 📈 Get coinstatus (trade) history for a specific token
FunctionTool.from_defaults(
    fn=lambda name: get_coinstatuses_by_coin_name(str(name)),
    name="query_coinstatuses_by_coin_name",
    description=(
        "Returns trade activity for a token.\n"
        "Each `record` contains:\n"
        "- holder: user ID\n"
        "- holdingStatus: 0 (buy), 1 (sell), 2 (launch), 3 (migrate)\n"
        "- amount (input), amountOut (output)\n"
        "- tx: transaction\n"
        "- time: timestamp"
    )
),

# 🔁 Get coinstatus by user
FunctionTool.from_defaults(
    fn=lambda user_id: get_coinstatuses_by_user_id(str(user_id)),
    name="query_coinstatuses_by_user_id",
    description=(
        "Returns trade history for a user.\n"
        "Each trade includes: coinId, holdingStatus, amount, amountOut, tx, time"
    )
),

# 🎟️ Scratch ticket history
FunctionTool.from_defaults(
    fn=lambda wallet: get_scratchhistories_by_wallet(str(wallet)),
    name="get_scratchhistories_by_wallet",
    description=(
        "Returns recent scratch ticket plays for a wallet.\n"
        "Each includes:\n"
        "- wNumbers (winning numbers), yNumbers (user’s picks)\n"
        "- winnings: amount won\n"
        "- wonFreeCard: bool\n"
        "- createdAt: timestamp"
    )
),

# 🎰 Spin history
FunctionTool.from_defaults(
    fn=lambda wallet: get_spinhistories_by_wallet(str(wallet)),
    name="get_spinhistories_by_wallet",
    description=(
        "Returns spin game history for a user wallet.\n"
        "Each includes:\n"
        "- spin ID, balance, matches, winnings\n"
        "- createdAt, updatedAt: timestamps"
    )
),

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

    "✨ Rule of paw: fetch only what’s helpful. Format it like royalty. Respond like the Web3 hype cat you are. 😸"
)


    )
