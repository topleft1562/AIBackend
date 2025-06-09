from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.agent import OpenAIAgent
from llama_index.llms.openai import OpenAI
import os

# Load documents if needed for context (optional)
def get_agent_runner():
    # Load OpenAI LLM
    llm = OpenAI(model="gpt-4", temperature=0.3)

    # Optionally load documents for background (disabled in this simple version)
    # documents = SimpleDirectoryReader("docs").load_data()
    # index = VectorStoreIndex.from_documents(documents)
    # return OpenAIAgent.from_tools(tools=[], llm=llm, verbose=True, context=index.as_query_engine())

    # Simple no-context agent
    return OpenAIAgent.from_tools(tools=[], llm=llm, verbose=True)
