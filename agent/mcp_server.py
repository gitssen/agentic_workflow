"""
MCP Server: Exposes Python functions as standardized MCP Tools.
This server acts as the execution environment for tools, providing
them with local capabilities (like SubAgents) to solve complex tasks.
"""

import os
import inspect
import importlib.util
import asyncio
import json
from typing import Any, Dict, List, Optional
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import sys
# Ensure the project root is in sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agent.config import setup_logger, MODEL_ID, EMBEDDING_MODEL_ID, FIRESTORE_DATABASE_ID
from agent.agent_logic import SubAgent

logger = setup_logger("MCPServer")

# --- 1. Infrastructure Initialization ---
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

class ToolManager:
    """
    Manages the lifecycle, discovery, and execution of local tools.
    Provides Tool-RAG capabilities for internal SubAgents.
    """
    def __init__(self, tools_dir: str = None):
        if tools_dir is None:
            # Use the 'tools' directory within the same folder as this file
            tools_dir = os.path.join(os.path.dirname(__file__), "tools")
        self.tools_dir = tools_dir
        self.tools = {}
        self.collection = db.collection("tools")
        self.load_tools()

    def load_tools(self):
        """Scans the tools directory and imports all Python functions."""
        logger.debug(f"Loading tools from {self.tools_dir}. sys.path: {sys.path}")
        if not os.path.exists(self.tools_dir):
            logger.error(f"Tools directory '{self.tools_dir}' not found.")
            return
            
        for filename in os.listdir(self.tools_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                # Use absolute import path for tools
                full_module_name = f"agent.tools.{module_name}"
                file_path = os.path.join(self.tools_dir, filename)
                spec = importlib.util.spec_from_file_location(full_module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                # Ensure the module knows it's part of the package
                module.__package__ = "agent.tools"
                spec.loader.exec_module(module)
                
                for name, obj in inspect.getmembers(module):
                    # We accept both sync and async functions
                    if (inspect.isfunction(obj) or inspect.iscoroutinefunction(obj)) and obj.__module__ == full_module_name:
                        self.tools[name] = obj
                        logger.info(f"Loaded tool: {name}")

    async def get_relevant_tools(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Performs Vector Search (RAG) in Firestore for internal sub-tasks.
        This allows SubAgents running inside the server to find tools dynamically.
        """
        from agent.config import get_genai_client
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

    def get_mcp_tool_list(self) -> List[Tool]:
        """Translates Python metadata into MCP Tool JSON Schemas."""
        mcp_tools = []
        for name, func in self.tools.items():
            sig = inspect.signature(func)
            doc = func.__doc__.strip() if func.__doc__ else "No description available."
            
            # Map Python parameters to JSON Schema
            properties = {}
            required = []
            for p_name, p in sig.parameters.items():
                if p_name == "sub_agent":
                    continue # Internal capability, not exposed via MCP JSON
                
                # Infer type from annotation or default value
                p_type = "string"
                if p.annotation == int:
                    p_type = "integer"
                elif p.annotation == float:
                    p_type = "number"
                elif p.annotation == bool:
                    p_type = "boolean"
                elif p.default != inspect.Parameter.empty:
                    if isinstance(p.default, int):
                        p_type = "integer"
                    elif isinstance(p.default, float):
                        p_type = "number"
                    elif isinstance(p.default, bool):
                        p_type = "boolean"

                properties[p_name] = {"type": p_type, "description": p_name}
                if p.default == inspect.Parameter.empty:
                    required.append(p_name)

            mcp_tools.append(Tool(
                name=name,
                description=doc, 
                inputSchema={"type": "object", "properties": properties, "required": required}
            ))
        return mcp_tools

# --- 2. MCP Server Configuration ---
server = Server("agentic-workflow-tools")
tool_manager = ToolManager()

async def internal_execute(name: str, args: Dict[str, Any]) -> str:
    """
    Executes a tool within the server context.
    Handles 'sub_agent' injection and async/sync execution.
    Also handles mapping 'query' to the first parameter for robustness.
    """
    if name not in tool_manager.tools:
        return f"Error: Tool {name} not found."
        
    func = tool_manager.tools[name]
    sig = inspect.signature(func)
    
    # Prepare arguments
    kwargs = args or {}
    
    # Robustness: Map 'query' to the first parameter if it exists and is missing
    if "query" in kwargs and len(sig.parameters) > 0:
        first_param = list(sig.parameters.keys())[0]
        if first_param not in kwargs and first_param != "sub_agent":
            kwargs[first_param] = kwargs.pop("query")

    if "sub_agent" in sig.parameters:
        # Provide a SubAgent that knows how to call other tools on THIS server
        sub = SubAgent(tool_manager, MODEL_ID, depth=1, execute_func=internal_execute)
        kwargs["sub_agent"] = sub
    
    # Final filtering: Only pass arguments that the function actually accepts
    valid_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
    
    # Execute and handle both synchronous and asynchronous tools
    if inspect.iscoroutinefunction(func):
        result = await func(**valid_kwargs)
    else:
        result = func(**valid_kwargs)
    
    return str(result)

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """Exposes the internal tools to any connected MCP Host."""
    return tool_manager.get_mcp_tool_list()

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any] | None) -> List[TextContent]:
    """Standard MCP entry point for tool execution."""
    logger.debug(f"Incoming MCP Call: {name}({arguments})")
    try:
        result = await internal_execute(name, arguments or {})
        return [TextContent(type="text", text=result)]
    except Exception as e:
        logger.error(f"Execution Error in {name}: {str(e)}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    """Starts the MCP server on Stdio transport."""
    try:
        logger.info("Starting MCP Server (Stdio)...")
        async with stdio_server() as (read, write):
            logger.debug("Stdio streams established. Running server...")
            await server.run(read, write, server.create_initialization_options())
    except Exception as e:
        logger.critical(f"FATAL: MCP Server crashed during startup/run: {e}", exc_info=True)
        with open("mcp_crash.log", "a") as f:
            import traceback
            f.write(f"Crash: {e}\n{traceback.format_exc()}\n")
        raise

if __name__ == "__main__":
    asyncio.run(main())
