import os
import sys
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Add the project root directory to the path so we can import 'agent' as a package
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from agent.agent_logic import GenericReActAgent, load_persona
from agent.config import setup_logger, FIRESTORE_DATABASE_ID

# Initialize FastAPI and Logger
app = FastAPI(title="Agentic Workflow Bridge")
logger = setup_logger("Backend")

# CORS Configuration for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MCP Client Management ---
class MCPManager:
    """Manages a persistent connection to the MCP Server."""
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._exit_stack = None

    async def connect(self):
        mcp_path = os.path.join(os.path.dirname(__file__), "..", "agent", "mcp_server.py")
        logger.info(f"Starting MCP Server from: {mcp_path}")
        server_params = StdioServerParameters(
            command="./.venv/bin/python3",
            args=[mcp_path],
            env={**os.environ}
        )
        # Note: stdio_client is an async context manager. 
        # For a persistent backend, we use it to start the server.
        self._client_gen = stdio_client(server_params)
        read, write = await self._client_gen.__aenter__()
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()
        logger.info("Connected to MCP Server")

    async def disconnect(self):
        if self.session:
            await self.session.__aexit__(None, None, None)
        if self._client_gen:
            await self._client_gen.__aexit__(None, None, None)
        logger.info("Disconnected from MCP Server")

mcp_manager = MCPManager()

@app.on_event("startup")
async def startup_event():
    await mcp_manager.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await mcp_manager.disconnect()

# --- Registry for the Agent ---
# We reuse the Firestore-based registry from the agent package
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

class BackendRegistry:
    def __init__(self, collection_name: str = "tools"):
        self.collection = db.collection(collection_name)

    async def get_relevant_tools(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        from agent.config import get_genai_client, EMBEDDING_MODEL_ID
        client = get_genai_client()
        embedding_response = client.models.embed_content(
            model=EMBEDDING_MODEL_ID, contents=query, config={"output_dimensionality": 768}
        )
        query_vector = embedding_response.embeddings[0].values
        results = self.collection.find_nearest(
            vector_field="embedding", query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE, limit=limit
        ).get()
        return [doc.to_dict() for doc in results]

# --- API Models ---
class ChatRequest(BaseModel):
    message: str
    persona: str = "general"

class ChatResponse(BaseModel):
    response: str
    thought: Optional[str] = None

# --- Endpoints ---
@app.get("/personas")
async def get_personas():
    """Lists available personas from the agent/prompts directory."""
    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "agent", "prompts")
    if not os.path.exists(prompts_dir):
        logger.warning(f"Prompts directory not found: {prompts_dir}")
        return ["general"]
    personas = [f[:-3] for f in os.listdir(prompts_dir) if f.endswith(".md")]
    logger.info(f"Returning personas: {personas}")
    return personas

import json

@app.post("/chat")
async def chat(request: ChatRequest):
    """Sends a message to the agent and returns a stream of reasoning steps."""
    if not mcp_manager.session:
        raise HTTPException(status_code=503, detail="MCP Server not connected")

    async def execute_via_mcp(name, args):
        logger.debug(f"Executing MCP Tool: {name} with args: {args}")
        try:
            res = await mcp_manager.session.call_tool(name, args)
            return res.content[0].text
        except Exception as e:
            logger.error(f"MCP Tool Call Error ({name}): {e}")
            raise

    registry = BackendRegistry()
    agent = GenericReActAgent(registry, execute_via_mcp, persona=request.persona)
    
    async def event_generator():
        try:
            async for step in agent.run(request.message):
                # We yield each step as a JSON string for the frontend to parse
                yield f"data: {json.dumps(step)}\n\n"
        except Exception as e:
            logger.error(f"Agent Error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
