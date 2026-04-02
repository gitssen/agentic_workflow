import asyncio
import json
import os
from typing import Any, Dict, List
from agent.agent_logic import GenericReActAgent

# LangChain/LangGraph usually looks for GOOGLE_API_KEY for Gemini
if "GEMINI_API_KEY" in os.environ and "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

class MockRegistry:
    async def get_relevant_tools(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        return [{
            "name": "search_web",
            "description": "Searches the live web using Google Search.",
            "full_doc": "search_web(query: str, num_results: int = 3): Searches the live web.",
            "signature": "(query: str, num_results: int = 3)",
            "properties": {
                "query": {"type": "string", "description": "query"},
                "num_results": {"type": "integer", "description": "num_results"}
            },
            "required": ["query"]
        }]

async def mock_execute(name: str, args: Dict[str, Any]) -> str:
    print(f"  [Mock Execute] Tool: {name}, Args: {args}")
    if name == "search_web":
        return "Apollo 11 mission facts: Launched July 16, 1969. Crew: Neil Armstrong, Buzz Aldrin, Michael Collins. Landed on Moon July 20, 1969. Sea of Tranquility."
    return "Tool not found"

async def test_run():
    registry = MockRegistry()
    agent = GenericReActAgent(registry, mock_execute)
    
    print("\n--- Starting LangGraph Test Run ---")
    query = "write a blog post in the style of edgar allen poe limiting yourself to 400 words about the moon landing"
    print(f"User Query: {query}")
    
    async for step in agent.run(query):
        step_type = step["type"]
        content = step["content"]
        
        if step_type == "thought":
            print(f"Thought: {content}")
        elif step_type == "action":
            print(f"Action: {step['tool']} with {step['args']}")
        elif step_type == "observation":
            print(f"Observation: {content}")
        elif step_type == "final_answer":
            print(f"Final Answer: {content}")
        elif step_type == "error":
            print(f"Error: {content}")

if __name__ == "__main__":
    asyncio.run(test_run())
