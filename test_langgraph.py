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
        # Return metadata for a fake weather tool
        return [{
            "name": "get_weather",
            "description": "Fetches weather data for a location.",
            "full_doc": "get_weather(location: str): Fetches weather data for a location.",
            "signature": "(location: str)"
        }]

async def mock_execute(name: str, args: Dict[str, Any]) -> str:
    print(f"  [Mock Execute] Tool: {name}, Args: {args}")
    if name == "get_weather":
        return json.dumps({"location": args.get("location", "unknown"), "temp_c": 22, "condition": "Sunny"})
    return "Tool not found"

async def test_run():
    registry = MockRegistry()
    # We use a depth of 0 and the default 'general' persona
    agent = GenericReActAgent(registry, mock_execute)
    
    print("\n--- Starting LangGraph Test Run ---")
    query = "What is the weather in Paris?"
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
