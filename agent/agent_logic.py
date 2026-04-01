"""
Agent Logic Module: Implements the core ReAct framework using LangGraph.
This version replaces the manual loop with a compiled StateGraph for better 
state management and future multi-agent scalability.
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional, Annotated, Sequence, TypedDict, Union, Type
from pydantic import BaseModel, Field, create_model

# LangChain & LangGraph Imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import Tool as LCTool, StructuredTool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.runnables import RunnableConfig

from agent.config import setup_logger, MODEL_ID

def load_persona(name: str = "general") -> str:
    """Loads a persona description from the prompts directory."""
    try:
        # Get the directory where this file resides
        base_dir = os.path.dirname(__file__)
        path = os.path.join(base_dir, "prompts", f"{name}.md")
        if not os.path.exists(path):
            logger.warning(f"Persona '{name}' not found. Falling back to 'general'.")
            path = os.path.join(base_dir, "prompts", "general.md")
            
        with open(path, "r") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error loading persona '{name}': {e}")
        return "You are a helpful AI assistant."

logger = setup_logger("AgentLogic")

# Ensure API Key is available for LangChain (which defaults to GOOGLE_API_KEY)
if "GEMINI_API_KEY" in os.environ and "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# --- 1. State Definition ---
class AgentState(TypedDict):
    """The state of the agent graph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    persona_text: str
    tools: List[LCTool]

# --- 2. Tool Wrapper ---
def create_tool_wrapper(name: str, description: str, execute_func: Any, metadata: Dict[str, Any]):
    """Wraps an MCP tool execution function into a LangChain StructuredTool using metadata."""
    async def _arun(**kwargs):
        # StructuredTool passes arguments as kwargs
        return await execute_func(name, kwargs)

    # Reconstruct the schema from metadata
    properties = metadata.get("properties", {})
    required = metadata.get("required", [])
    
    # Map types to Python types
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool
    }
    
    fields = {}
    for p_name, p_info in properties.items():
        # Gemini works best with string types if we are unsure
        # We also add a description to help the model
        if p_name in required:
            fields[p_name] = (str, Field(..., description=p_name))
        else:
            fields[p_name] = (str, Field(default="", description=p_name))
            
    # Create dynamic Pydantic model
    args_schema = create_model(f"{name}_args", **fields) if fields else None
    
    return StructuredTool.from_function(
        name=name,
        description=description,
        coroutine=_arun,
        func=lambda **kwargs: None,
        args_schema=args_schema
    )

# --- 3. LangGraph ReAct Agent ---
class GenericReActAgent:
    def __init__(self, registry: Any, execute_func: Any, model_id: str = MODEL_ID, depth: int = 0, persona: str = "general"):
        self.registry = registry
        self.execute_func = execute_func
        self.depth = depth
        self.persona_name = persona
        self.persona_text = load_persona(persona)
        
        # Initialize the LangChain LLM
        # Note: We use MODEL_ID from config, but LangChain uses 'models/name' format for Gemini
        langchain_model = model_id if model_id.startswith("models/") else f"models/{model_id}"
        self.llm = ChatGoogleGenerativeAI(
            model=langchain_model,
            temperature=0
        )
        
        self.graph = None

    def _build_graph(self, tools: List[LCTool]):
        """Builds and compiles the LangGraph StateGraph."""
        workflow = StateGraph(AgentState)

        # Define the nodes
        async def call_model(state: AgentState, config: RunnableConfig):
            # Prepend system message for persona
            messages = [SystemMessage(content=state["persona_text"])] + list(state["messages"])
            llm_with_tools = self.llm.bind_tools(state["tools"])
            response = await llm_with_tools.ainvoke(messages, config)
            return {"messages": [response]}

        async def execute_tools(state: AgentState):
            last_message = state["messages"][-1]
            tool_messages = []
            
            for tool_call in last_message.tool_calls:
                tool = next(t for t in state["tools"] if t.name == tool_call["name"])
                observation = await tool.ainvoke(tool_call["args"])
                tool_messages.append(ToolMessage(
                    content=str(observation),
                    tool_call_id=tool_call["id"]
                ))
            
            return {"messages": tool_messages}

        def should_continue(state: AgentState):
            last_message = state["messages"][-1]
            if last_message.tool_calls:
                return "tools"
            return END

        workflow.add_node("agent", call_model)
        workflow.add_node("tools", execute_tools)

        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    async def run_full(self, user_input: str) -> str:
        """Helper to run the agent to completion and return only the final answer."""
        final_answer = "Max reasoning steps reached."
        async for step in self.run(user_input):
            if step["type"] == "final_answer":
                final_answer = step["content"]
        return final_answer

    async def run(self, user_input: str):
        """
        Asynchronous generator that yields each step of the reasoning process.
        Uses astream_events to provide token-level thought streaming.
        """
        # Safety: check depth
        if self.depth > 3:
            yield {"type": "error", "content": "Maximum recursion depth reached."}
            return

        # 1. Tool Discovery (Tool-RAG)
        relevant_tool_metadata = await self.registry.get_relevant_tools(user_input)
        lc_tools = [
            create_tool_wrapper(t["name"], t.get("full_doc", t["description"]), self.execute_func, t)
            for t in relevant_tool_metadata
        ]

        # 2. Setup Graph and State
        graph = self._build_graph(lc_tools)
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "persona_text": self.persona_text,
            "tools": lc_tools
        }

        # 3. Stream Events
        # We use astream_events to get both node updates and token chunks
        indent = "  " * self.depth
        current_thought = ""
        
        async for event in graph.astream_events(initial_state, version="v2"):
            kind = event["event"]
            
            # --- Handle Token Streaming (Thoughts) ---
            if kind == "on_chat_model_stream" and self.depth == 0:
                # We only stream tokens for the top-level agent to avoid UI clutter
                content = event["data"]["chunk"].content
                if isinstance(content, str) and content:
                    current_thought += content
                    yield {"type": "thought", "content": current_thought}
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            current_thought += part["text"]
                            yield {"type": "thought", "content": current_thought}

            # --- Handle Node Updates (Actions, Observations, Final Answers) ---
            elif kind == "on_chain_end" and event["name"] == "LangGraph":
                # The final output of the graph is sometimes useful but we usually 
                # get better detail from node-level updates.
                pass

            elif kind == "on_node_end":
                node_name = event["name"]
                output = event["data"]["output"]
                
                if node_name == "agent":
                    message = output["messages"][-1]
                    
                    # If we weren't streaming tokens, or if this is an action, yield it
                    if message.tool_calls:
                        for tc in message.tool_calls:
                            yield {
                                "type": "action", 
                                "content": f"{indent}Using tool: {tc['name']}", 
                                "tool": tc['name'], 
                                "args": tc['args']
                            }
                            yield {
                                "type": "delegation",
                                "content": f"{indent}Delegating to {tc['name']}..."
                            }
                    elif not current_thought:
                        # Fallback for non-streaming models or hidden reasoning
                        final_text = self._flatten_content(message.content)
                        yield {"type": "thought", "content": final_text}
                        
                    # If no tool calls, it's the final answer for THIS agent/sub-agent
                    if not message.tool_calls:
                        final_text = self._flatten_content(message.content)
                        yield {"type": "final_answer", "content": final_text}

                elif node_name == "tools":
                    for msg in output["messages"]:
                        yield {"type": "observation", "content": msg.content}

    def _flatten_content(self, content: Union[str, list]) -> str:
        """Helper to convert Gemini message content to a clean string."""
        if isinstance(content, str):
            return content
        res = ""
        if isinstance(content, list):
            for part in content:
                if isinstance(part, str):
                    res += part
                elif isinstance(part, dict) and part.get("type") == "text":
                    res += part.get("text", "")
        return res

class SubAgent:
    """Compatibility wrapper for recursive reasoning."""
    def __init__(self, registry: Any, model_id: str, depth: int, execute_func: Any, persona: str = "general"):
        self.registry = registry
        self.model_id = model_id
        self.depth = depth
        self.execute_func = execute_func
        self.persona = persona

    async def solve(self, goal: str) -> str:
        agent = GenericReActAgent(self.registry, self.execute_func, self.model_id, depth=self.depth + 1, persona=self.persona)
        return await agent.run_full(goal)
