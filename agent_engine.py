import os
from dotenv import load_dotenv
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionCallingAgent
from llama_index.core.tools import FunctionTool

load_dotenv()

llm = OpenAI(
    model="gpt-4.1-mini",
)

def get_agent_runner():
    return FunctionCallingAgent.from_tools(
        tools=[],  # No tools needed, just reasoning
        llm=llm,
        system_prompt=(
            "You are Dispatchy, a highly efficient logistics planner for a trucking company. "
            "You are an expert at reducing empty miles, optimizing driver assignments, and creating the most efficient routes possible with the provided load and route data. "
            "Always prioritize minimizing empty distance and maximizing efficiency in your plans."
        )
    )

    

