"""
MCP Host: The primary entry point for the agentic workflow.
Acts as an MCP Client that connects to the tool server.
Now supports Persona Selection.
"""

import os
import asyncio
import readline
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import firestore
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from agent.config import setup_logger, MODEL_ID, EMBEDDING_MODEL_ID, FIRESTORE_DATABASE_ID
from agent.agent_logic import GenericReActAgent
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

# Load environment variables (.env)
load_dotenv()
logger = setup_logger("MCPHost")

# History file configuration
HISTORY_FILE = ".agent_history"

def setup_history():
    if os.path.exists(HISTORY_FILE):
        try:
            readline.read_history_file(HISTORY_FILE)
        except Exception:
            pass
    readline.set_history_length(1000)

def save_history():
    try:
        readline.write_history_file(HISTORY_FILE)
    except Exception:
        pass

setup_history()

# --- 1. Infrastructure Initialization ---
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

class HostRegistry:
    def __init__(self, collection_name: str = "tools"):
        self.collection = db.collection(collection_name)

    async def get_relevant_tools(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        from agent.config import get_genai_client, EMBEDDING_MODEL_ID, EMBEDDING_DIM
        client = get_genai_client()
        embedding_response = client.models.embed_content(
            model=EMBEDDING_MODEL_ID, contents=query, config={"output_dimensionality": EMBEDDING_DIM}
        )
        query_vector = embedding_response.embeddings[0].values
        results = self.collection.find_nearest(
            vector_field="embedding", query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE, limit=limit
        ).get()
        return [doc.to_dict() for doc in results]

def select_persona() -> str:
    """Prompts the user to select a persona from the prompts/ directory."""
    prompts_dir = "prompts"
    if not os.path.exists(prompts_dir):
        return "general"
    
    files = [f[:-3] for f in os.listdir(prompts_dir) if f.endswith(".md")]
    if not files:
        return "general"
    
    print("\n--- Available Personas ---")
    for i, f in enumerate(files, 1):
        print(f"{i}. {f}")
    
    try:
        choice = input("\nSelect a persona (number) or press Enter for 'general' > ").strip()
        if not choice:
            return "general"
        idx = int(choice) - 1
        if 0 <= idx < len(files):
            return files[idx]
    except Exception:
        pass
    
    return "general"

async def main():
    persona = select_persona()
    logger.info(f"Active Persona: {persona}")

    server_params = StdioServerParameters(
        command="../venv/bin/python3",
        args=["mcp_server.py"],
        env={**os.environ}
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            async def execute_via_mcp(name, args):
                res = await session.call_tool(name, args)
                return res.content[0].text

            registry = HostRegistry()
            # Pass the selected persona to the agent
            agent = GenericReActAgent(registry, execute_via_mcp, persona=persona)
            logger.info(f"--- MCP Host Ready ({persona}) ---")

            while True:
                try:
                    query = input(f"\n[{persona}] User > ").strip()
                    if query.lower() in ["exit", "quit"]: break
                    if query: 
                        save_history()
                        result = await agent.run(query)
                        logger.info(f"Result > {result}")
                except (EOFError, KeyboardInterrupt):
                    break
                except Exception as e: 
                    logger.error(f"Runtime Error: {e}")
                    # If we hit a persistent I/O error (like Errno 5), the terminal is likely gone.
                    # Breaking here prevents a tight loop that would flood the logs.
                    if "[Errno 5]" in str(e):
                        break

if __name__ == "__main__":
    asyncio.run(main())
