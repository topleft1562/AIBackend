from llama_index.llms.openai import OpenAI
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.tools import FunctionTool
from dotenv import load_dotenv
import os

load_dotenv()

llm = OpenAI(model="gpt-4.1")

def get_agent_runner():
    return FunctionAgent(
        tools=[],  # Add FunctionTool.from_defaults(fn=your_function) if needed
        llm=llm,
        system_prompt=(
            "You are Dispatchy, a highly efficient logistics planner for a trucking company. "
            "You are an expert at reducing empty miles, optimizing driver assignments, and creating the most efficient routes possible with the provided load and route data. "
            "Always prioritize minimizing empty distance and maximizing efficiency in your plans."
        ),
        verbose=True
    )
