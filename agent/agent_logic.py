"""
Agent Logic Module: Implements a Hierarchical Multi-Agent System using LangGraph.
A 'Supervisor' agent evaluates a shared 'Artifact' and routes to specialized agents.
"""

import os
import json
import asyncio
import re
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

if "GEMINI_API_KEY" in os.environ and "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# --- 1. State Definition ---
class AgentState(TypedDict):
    """
    The persistent state of the multi-agent graph.
    Acts as the 'Shared Memory' for all specialists and the supervisor.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages] # History of turns
    tools: List[LCTool]                                     # Available MCP capabilities
    active_specialist: Optional[str]                        # Who is currently thinking
    artifact: Optional[str]                                 # The Blackboard: Current work product
    eval_feedback: Optional[str]                            # Instructions from the Supervisor
    is_approved: bool                                       # Termination condition
    loop_count: int                                         # Prevention of infinite routing loops

# --- Supervisor Output Schema ---
class SupervisorDecision(BaseModel):
    """Schema for the Supervisor's routing decision."""
    is_approved: bool = Field(description="True if the artifact perfectly fulfills the user request. False otherwise.")
    eval_feedback: str = Field(description="Detailed feedback on what is missing or needs fixing. Empty if approved.")
    next_specialist: str = Field(description="The exact name of the specialist to route to if not approved (e.g., 'music_curator', 'blog_writer').")

# --- 2. Tool Wrapper ---
def create_tool_wrapper(name: str, description: str, execute_func: Any, metadata: Dict[str, Any]):
    """Wraps an MCP tool execution function into a LangChain StructuredTool."""
    async def _arun(**kwargs):
        return await execute_func(name, kwargs)

    properties = metadata.get("properties", {})
    required = metadata.get("required", [])
    
    # Map JSON schema types to Python types for Pydantic validation
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool
    }
    
    fields = {}
    for p_name, p_info in properties.items():
        p_type = type_map.get(p_info.get("type", "string"), str)
        if p_name in required:
            fields[p_name] = (p_type, Field(..., description=p_name))
        else:
            fields[p_name] = (Optional[p_type], Field(default=None, description=p_name))
            
    args_schema = create_model(f"{name}_args", **fields) if fields else None
    
    return StructuredTool.from_function(
        name=name,
        description=description,
        coroutine=_arun,
        func=lambda **kwargs: None,
        args_schema=args_schema
    )

# --- 3. Master Multi-Agent System ---
class GenericReActAgent:
    def __init__(self, registry: Any, execute_func: Any, model_id: str = MODEL_ID, depth: int = 0, persona: str = "general", strict_persona: bool = False):
        self.registry = registry
        self.execute_func = execute_func
        self.depth = depth
        self.persona_name = persona
        self.strict_persona = strict_persona
        
        langchain_model = model_id if model_id.startswith("models/") else f"models/{model_id}"
        self.llm = ChatGoogleGenerativeAI(model=langchain_model, temperature=0)
        self.graph = None

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        # --- Node: Supervisor ---
        async def supervisor_node(state: AgentState):
            """
            Evaluates the current Artifact against the user request.
            Acts as the router and quality controller.
            """
            loop_count = state.get("loop_count", 0) + 1
            
            # Extraction of core user intent
            user_request = next((m.content for m in state["messages"] if isinstance(m, HumanMessage)), "")
            artifact = state.get("artifact", "")
            
            logger.info(f"--- Supervisor Node Starting (Loop: {loop_count}) ---")
            
            if loop_count > 3:
                logger.warning("Maximum routing loops reached. Forcing termination.")
                return {
                    "is_approved": True,
                    "eval_feedback": "Stopped: No progress made after multiple attempts.",
                    "loop_count": loop_count
                }

            logger.info(f"Current Artifact length: {len(artifact) if artifact else 0}")
            if state.get("eval_feedback"):
                logger.info(f"Previous Feedback: {state['eval_feedback'][:100]}...")

            persona = load_persona("supervisor")
            
            # If no artifact was found, we show the supervisor what the last agent said
            # so it can diagnose why the extraction failed.
            last_msg = state["messages"][-1] if state["messages"] else None
            last_content = self._flatten_content(last_msg.content) if last_msg else ""
            
            prompt = f"{persona}\n\nUSER REQUEST: {user_request}\n\nCURRENT ARTIFACT:\n{artifact if artifact else '[None yet]'}"
            
            if not artifact and last_content:
                prompt += f"\n\nLAST AGENT RESPONSE (Note: No artifact was extracted from this):\n{last_content}"

            # History Management: Gemini requires history to end with a HumanMessage
            # when performing Tool Calls (Structured Output). We build a clean turn history here.
            eval_request = HumanMessage(content=prompt)
            context_messages = [SystemMessage(content=load_persona("supervisor"))]
            
            first_human = next((m for m in state["messages"] if isinstance(m, HumanMessage)), None)
            if first_human:
                context_messages.append(first_human)
            
            # Final message is ALWAYS Human to ensure model compliance
            context_messages.append(eval_request)
            
            eval_llm = self.llm.with_structured_output(SupervisorDecision).with_config({"tags": ["supervisor"]})
            decision = await eval_llm.ainvoke(context_messages)
            
            next_specialist = self.persona_name if self.strict_persona else decision.next_specialist
            logger.info(f"Supervisor Decision: approved={decision.is_approved}, next={next_specialist}")
            
            return {
                "is_approved": decision.is_approved,
                "eval_feedback": decision.eval_feedback,
                "active_specialist": next_specialist,
                "loop_count": loop_count
            }

        # --- Node: Specialist Agent ---
        async def call_specialist(state: AgentState, config: RunnableConfig):
            """
            Invokes specialized LLM personas.
            Uses 'Context Isolation' to prevent reasoning loops from large histories.
            """
            specialist_name = state.get("active_specialist", "general")
            last_msg = state["messages"][-1] if state["messages"] else None
            is_returning_from_tool = isinstance(last_msg, ToolMessage)
            
            if is_returning_from_tool:
                logger.info(f"Specialist '{specialist_name}' receiving tool output.")
            else:
                logger.info(f"Specialist '{specialist_name}' starting task.")

            persona = load_persona(specialist_name)
            
            # Injection of the shared state (Artifact and Feedback) into the specialist prompt
            context = f"CURRENT ARTIFACT:\n{state.get('artifact', '[None]')}\n\nSUPERVISOR FEEDBACK:\n{state.get('eval_feedback', 'Create the initial artifact.')}\n\nCRITICAL: If you are NOT calling a tool, you MUST wrap your final output in <artifact>...</artifact> tags. Even if you only made minor changes, output the COMPLETE NEW ARTIFACT."
            
            # --- History Management (Isolation) ---
            # Specialists only see: System Prompt + Original Request + current tool-loop turns.
            # This prevents them from being confused by previous specialist attempts.
            messages = [SystemMessage(content=f"{persona}\n\n{context}")]
            
            first_human = next((m for m in state["messages"] if isinstance(m, HumanMessage)), None)
            if first_human:
                messages.append(first_human)
            
            # If in a tool loop, include the sequence: AI(calls) -> Tool(results)
            if is_returning_from_tool:
                found_first_tool_call = False
                for m in state["messages"]:
                    if not found_first_tool_call:
                        if isinstance(m, AIMessage) and m.tool_calls:
                            found_first_tool_call = True
                            messages.append(m)
                    else:
                        messages.append(m)
            
            llm_with_tools = self.llm.bind_tools(state["tools"]).with_config({"tags": ["specialist"]})
            response = await llm_with_tools.ainvoke(messages, config)
            
            logger.info(f"Specialist '{specialist_name}' response received. Length: {len(response.content) if response.content else 0}")

            updates = {"messages": [response]}
            
            # Blackboard Update: Extract the artifact if present
            if response.content:
                text = self._flatten_content(response.content)
                match = re.search(r"<artifact>(.*?)</artifact>", text, re.DOTALL)
                if match:
                    logger.info(f"Specialist '{specialist_name}' produced artifact. Length: {len(match.group(1))}")
                    updates["artifact"] = match.group(1).strip()
                elif not response.tool_calls and specialist_name != "general":
                    # Heuristic Fallback: Specialists often forget tags. If they didn't call tools,
                    # we treat their raw text as the new artifact to avoid empty-state loops.
                    if len(text.strip()) > 100:
                        logger.warning(f"Specialist '{specialist_name}' forgot <artifact> tags. Using raw content.")
                        updates["artifact"] = text.strip()
            
            return updates

        # --- Node: Tool Executor ---
        async def execute_tools(state: AgentState):
            """Executes any tool calls generated by the specialist."""
            last_message = state["messages"][-1]
            tool_messages = []
            for tool_call in last_message.tool_calls:
                tool = next((t for t in state["tools"] if t.name == tool_call["name"]), None)
                if not tool:
                    obs = f"Error: Tool {tool_call['name']} not found."
                else:
                    obs = await tool.ainvoke(tool_call["args"])
                
                tool_messages.append(ToolMessage(content=str(obs), tool_call_id=tool_call["id"]))
            return {"messages": tool_messages}

        # --- Logic: Routing ---
        def route_from_supervisor(state: AgentState):
            if state.get("is_approved"):
                logger.info(">>> Graph Routing: [Supervisor] -> [END]")
                return END
            spec = state.get("active_specialist", "general")
            logger.info(f">>> Graph Routing: [Supervisor] -> [Specialist: {spec}]")
            return "specialist"
            
        def route_from_specialist(state: AgentState):
            last_message = state["messages"][-1]
            if last_message.tool_calls:
                tools = [tc["name"] for tc in last_message.tool_calls]
                logger.info(f">>> Graph Routing: [Specialist] -> [Tools: {tools}]")
                return "tools"
            logger.info(">>> Graph Routing: [Specialist] -> [Supervisor]")
            return "supervisor"

        # --- Graph Construction ---
        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("specialist", call_specialist)
        workflow.add_node("tools", execute_tools)

        workflow.set_entry_point("supervisor")
        workflow.add_conditional_edges("supervisor", route_from_supervisor)
        workflow.add_conditional_edges("specialist", route_from_specialist)
        workflow.add_edge("tools", "specialist")

        return workflow.compile()

    async def run_full(self, user_input: str) -> str:
        """Helper to run the graph and return ONLY the final artifact."""
        final_answer = "Max reasoning steps reached."
        async for step in self.run(user_input):
            if step["type"] == "final_answer":
                final_answer = step["content"]
        return final_answer

    async def run(self, user_input: str):
        """Streams thought events from the graph execution for real-time UI display."""
        if self.depth > 3:
            yield {"type": "error", "content": "Maximum recursion depth reached."}
            return

        # Tool Retrieval (RAG)
        relevant_tool_metadata = await self.registry.get_relevant_tools(user_input, limit=10)
        lc_tools = [
            create_tool_wrapper(t["name"], t.get("full_doc", t["description"]), self.execute_func, t)
            for t in relevant_tool_metadata
        ]

        self.graph = self._build_graph()
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "tools": lc_tools,
            "active_specialist": None,
            "artifact": None,
            "eval_feedback": None,
            "is_approved": False,
            "loop_count": 0
        }

        indent = "  " * self.depth
        current_thought = ""
        yielded_final = False
        
        async for event in self.graph.astream_events(initial_state, version="v2", config={"recursion_limit": 100}):
            kind = event["event"]
            node_name = event.get("name")
            
            if kind == "on_node_end" and node_name == "supervisor":
                output = event["data"]["output"]
                if output.get("is_approved"):
                    yield {
                        "type": "thought",
                        "content": f"{indent}Supervisor: Artifact approved. Finishing."
                    }
                else:
                    specialist = output.get("active_specialist")
                    feedback = output.get("eval_feedback")
                    yield {
                        "type": "thought",
                        "content": f"{indent}Supervisor Feedback: {feedback}"
                    }
                    yield {
                        "type": "delegation",
                        "content": f"{indent}Supervisor routing to **{specialist.replace('_', ' ').title()}**..."
                    }

            elif kind == "on_chat_model_stream" and self.depth == 0 and "supervisor" not in event.get("tags", []):
                # Streaming individual thought chunks from specialist LLMs
                content = event["data"]["chunk"].content
                text_chunk = ""
                if isinstance(content, str):
                    text_chunk = content
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_chunk += part["text"]
                
                if text_chunk:
                    current_thought += text_chunk
                    if not current_thought.strip().startswith('{"is_approved":'):
                        yield {"type": "thought", "content": current_thought}

            elif kind == "on_node_end":
                output = event["data"]["output"]
                
                if node_name == "specialist":
                    message = output["messages"][-1]
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
                        yield {"type": "thought", "content": self._flatten_content(message.content)}
                    
                    current_thought = "" # Reset for next specialist turn

                elif node_name == "tools":
                    for msg in output["messages"]:
                        yield {"type": "observation", "content": msg.content}
                        
            elif kind == "on_chain_end" and (node_name == "LangGraph" or not node_name):
                # Final exit condition: provide the final artifact or feedback to the user.
                state = event.get("data", {}).get("output")
                if isinstance(state, dict) and "messages" in state and not yielded_final:
                    answer = state.get("artifact") or state.get("eval_feedback") or "Task completed."
                    yielded_final = True
                    yield {"type": "final_answer", "content": answer}

    def _flatten_content(self, content: Union[str, list]) -> str:
        """Helper to extract text from LangChain's potentially complex message content formats."""
        if isinstance(content, str): return content
        res = ""
        if isinstance(content, list):
            for part in content:
                if isinstance(part, str): res += part
                elif isinstance(part, dict) and part.get("type") == "text": res += part.get("text", "")
        return res

class SubAgent:
    """Capability for tools to recursively invoke the agentic workflow."""
    def __init__(self, registry: Any, model_id: str, depth: int, execute_func: Any, persona: str = "general"):
        self.registry = registry
        self.model_id = model_id
        self.depth = depth
        self.execute_func = execute_func
        self.persona = persona

    async def solve(self, goal: str) -> str:
        agent = GenericReActAgent(self.registry, self.execute_func, self.model_id, depth=self.depth + 1, persona=self.persona)
        return await agent.run_full(goal)
