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
            "You are Dispatchy — an efficient and focused AI dispatcher.\n\n"
            "Your only goals are:\n"
            "- Complete all loads using the fewest number of drivers possible.\n"
            "- Ensure each driver maintains at least a 70% loaded distance ratio.\n"
            "- Focus on minimizing empty kilometers.\n\n"
            "Each driver starts and ends at the base city.\n"
            "Use reload options to reduce deadhead between loads.\n\n"
            "For each driver, output:\n"
            "- Route: list of load IDs\n"
            "- Empty kilometers\n"
            "- Loaded kilometers\n"
            "- Loaded percent (loaded / (empty + loaded) * 100)\n"
            "- Estimated total hours (80 km/h average speed + 1 hour for load + 1 hour for unload per load)\n\n"
            "Ignore any concerns about time limits or weekly hour caps.\n"
            "Also include:\n"
            "- Recommendations on where to reduce empty miles (e.g., dropoffs with >100 km deadhead)\n"
            "- Suggestions for good reload pairings that were missed.\n\n"
            "Always return only the optimized plan."

        )
    )
