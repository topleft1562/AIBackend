from llama_index.llms.openai import OpenAI
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.tools import FunctionTool

llm = OpenAI(model="gpt-4.1")

# Optional example function
def get_distance(from_city: str, to_city: str) -> float:
    return 100.0  # dummy value

tools = [
    FunctionTool.from_defaults(fn=get_distance)
]

agent = FunctionAgent(
    tools=tools,
    llm=llm,
    system_prompt="You are Dispatchy, an expert logistics planner focused on maximizing efficiency.",
    verbose=True
)

