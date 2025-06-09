import os
from dotenv import load_dotenv
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent
from llama_index.core.tools import FunctionTool
from dispatch_planner import auto_dispatch_plan

load_dotenv()

llm = OpenAI(
    model="gpt-4.1-nano",
    temperature=0.7,
    frequency_penalty=0.3,
    presence_penalty=0.4
)

def get_agent_runner():
    tools = [
        FunctionTool.from_defaults(
            fn=auto_dispatch_plan,
            name="auto_dispatch_plan",
            description="Generate an optimized dispatch plan using only a list of loads and a base location."
        )
    ]

    return FunctionCallingAgent.from_tools(
        tools=tools,
        llm=llm,
        system_prompt=(
            "You are Dispatchy — an intelligent, no-nonsense AI dispatcher.\n\n"
            "Your job is to assign the fewest number of drivers needed to complete all loads efficiently.\n"
            "You calculate routes, minimize empty miles, return drivers to base, and avoid exceeding 70 hours.\n"
            "Aim to keep drivers under 55 hours where possible.\n\n"
            "📦 Input: a list of loads and a base city\n"
            "📋 Output: clear, driver-by-driver assignments with total km, hours, and HOS % used\n"
            "🚚 Always return drivers to base city.\n"
            "Do not ask questions. Respond only with the optimized plan."
        )
    )
