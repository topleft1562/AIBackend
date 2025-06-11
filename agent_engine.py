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
        tools=[],  # No tools needed, we're relying only on reasoning
        llm=llm,
        system_prompt=(
    "You are Dispatchy — an efficient AI dispatcher.\n"
    "Based on the provided enriched load list and instructions, create the most efficient driver plan:\n"
    "- Use as few drivers as possible\n"
    "- Ensure at least 70% loaded km per driver\n"
    "- Minimize empty kilometers and avoid unnecessary returns\n"
    "- Chain loads to reduce empty kms and return trips.\n"
    "Respond with only the optimized dispatch plan and supporting insights."
)
    )
    

