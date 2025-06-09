import os
from dotenv import load_dotenv
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent

from dispatch_tools.planner import generate_simple_dispatch_plan

load_dotenv()
llm = OpenAI(
    model="gpt-4.1-nano"
)

def get_agent_runner():
   

    tools = [
        FunctionTool.from_defaults(
            fn=generate_simple_dispatch_plan,
            name="generate_simple_dispatch_plan",
            description="Generate an optimized dispatch plan using a list of drivers (with location) and available loads. AI handles routing, distance calculations, and DOT compliance."
        )
    ]

    return FunctionCallingAgent.from_tools(
        tools=tools,
        llm=llm,
        system_prompt=(
            "You are Dispatchy — a smart AI dispatch assistant.\n\n"
            "📦 Task:\n"
            "- Accept:\n"
            "   → List of drivers (with names and current locations)\n"
            "   → List of loads (with pickup/dropoff locations and windows)\n"
            "- Plan routes that minimize empty kilometers and obey DOT 70/36 rules.\n"
            "- Use real-world distances and logic.\n\n"
            "🧾 Output Format:\n"
            "• Driver 1 (John - Brandon): Load1 → Load2 → Load3 (Total: 960km, 72% loaded)\n"
            "• Driver 2 (Sam - Regina): Load4 → reset\n\n"
            "💡 Tips:\n"
            "- Don’t ask for hours or limits — infer them\n"
            "- Keep things clean, optimized, and dispatcher-friendly\n"
            "- Ask for more info only if something critical is missing"
        )
    )
