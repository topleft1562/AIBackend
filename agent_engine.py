import os
from dotenv import load_dotenv
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent
from llama_index.core.tools import FunctionTool

load_dotenv()

llm = OpenAI(
    model="gpt-4.1-nano",
)

def get_agent_runner():
    return FunctionCallingAgent.from_tools(
        tools=[],  # No tools needed, we're relying only on reasoning
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
