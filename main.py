"""
MCP Host: The primary entry point for the agentic workflow.
Acts as an MCP Client that connects to the tool server and orchestrates
the high-level conversation using a ReAct reasoning loop.
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import firestore
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from config import setup_logger, MODEL_ID, EMBEDDING_MODEL_ID, FIRESTORE_DATABASE_ID
from agent_logic import GenericReActAgent
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

# Load environment variables (.env)
load_dotenv()
logger = setup_logger("MCPHost")

# --- 1. Infrastructure Initialization ---
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

class HostRegistry:
    """
    Registry used by the Host to perform Tool-RAG (Retrieval Augmented Generation).
    Retrieves the most semantically relevant tools from Firestore to minimize 
    context window usage and costs.
    """
    def __init__(self, collection_name: str = "tools"):
        self.collection = db.collection(collection_name)

    async def get_relevant_tools(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """
        Embeds the query and performs a vector search in Firestore.
        Returns top-N relevant tool metadata documents.
        """
        from config import get_genai_client
        client = get_genai_client()
        embedding_response = client.models.embed_content(
            model=EMBEDDING_MODEL_ID, contents=query, config={"output_dimensionality": 768}
        )
        query_vector = embedding_response.embeddings[0].values
        
        # Perform Vector Search (Requires Index on 'embedding' field)
        results = self.collection.find_nearest(
            vector_field="embedding", query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE, limit=limit
        ).get()
        return [doc.to_dict() for doc in results]

async def main():
    """
    Main entry point: 
    1. Connects to the MCP Server.
    2. Initializes the ReAct Agent.
    3. Starts the interactive CLI loop.
    """
    # Define connection parameters for the MCP Server
    server_params = StdioServerParameters(
        command="./venv/bin/python3",
        args=["mcp_server.py"],
        env={**os.environ} # Pass environment variables to the server process
    )

    # Establish the MCP connection (Stdio)
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the MCP Session (Handshake)
            await session.initialize()
            
            # Bridge function to execute tools via the MCP protocol
            async def execute_via_mcp(name, args):
                res = await session.call_tool(name, args)
                return res.content[0].text

            # Instantiate the Reasoning Agent
            registry = HostRegistry()
            agent = GenericReActAgent(registry, execute_via_mcp)
            logger.info("--- MCP Agent (Recursive Tool-RAG) Ready ---")

            # Interactive Chat Loop
            while True:
                try:
                    query = input("\nUser > ").strip()
                    if query.lower() in ["exit", "quit"]: break
                    if query: 
                        # Run the ReAct loop for the current question
                        result = await agent.run(query)
                        logger.info(f"Result > {result}")
                except KeyboardInterrupt: break
                except Exception as e: 
                    logger.error(f"Runtime Error: {e}")

if __name__ == "__main__":
    # Start the event loop
    asyncio.run(main())
