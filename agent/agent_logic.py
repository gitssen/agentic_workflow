"""
Agent Logic Module: Implements the core ReAct (Reasoning and Acting) framework.
This module is shared between the MCP Host and the MCP Server.
Now supports dynamic Personas via external prompt files.
"""

import os
import re
import json
import inspect
from typing import List, Dict, Any, Optional, Callable, Awaitable
from config import get_genai_client, MODEL_ID, setup_logger

logger = setup_logger("AgentLogic")

# --- 1. Base ReAct Protocol (Fixed) ---
# This part of the prompt NEVER changes, as it defines the "brain's" operating logic.
BASE_PROTOCOL = """
You solve problems by following a structured ReAct (Reasoning and Acting) loop.
You have access to the following tools:

{tool_definitions}

You MUST follow this exact format for every turn:

Thought: [Your reasoning about what to do next]
Action: [The name of the tool to use]
Action Input: [The JSON arguments for the tool]
Observation: [The result of the tool - THIS WILL BE PROVIDED TO YOU]

... (repeat Thought/Action/Action Input/Observation if needed)

Final Answer: [Your final response to the user, addressing their ORIGINAL query comprehensively]

Important: 
1. Only provide ONE Thought/Action/Action Input per turn. 
2. Wait for the Observation before continuing.
3. If you have enough information, provide the Final Answer immediately.
4. If you are missing information that cannot be resolved via tools (e.g. you need the user to provide a specific parameter), use 'Final Answer' to ask the user for that information.
5. Efficiency Rule: Prioritize '[Self-Resolving]' tools. If a tool can find its own missing data, call it directly.
"""

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

class SubAgent:
    def __init__(self, registry: Any, model_id: str, depth: int, execute_func: Callable[[str, Dict[str, Any]], Awaitable[str]], persona: str = "general"):
        self.registry = registry
        self.model_id = model_id
        self.depth = depth
        self.execute_func = execute_func
        self.persona = persona

    async def solve(self, goal: str) -> str:
        logger.debug(f"    [Sub-Agent (Depth {self.depth})] Goal: {goal}")
        # Sub-agents inherit the persona of their parent
        agent = GenericReActAgent(self.registry, self.execute_func, self.model_id, depth=self.depth, persona=self.persona)
        return await agent.run(goal)

class GenericReActAgent:
    def __init__(self, registry: Any, execute_func: Callable[[str, Dict[str, Any]], Awaitable[str]], model_id: str = MODEL_ID, depth: int = 0, persona: str = "general"):
        self.client = get_genai_client()
        self.model_id = model_id
        self.registry = registry
        self.execute_func = execute_func
        self.depth = depth
        self.persona_name = persona
        self.persona_text = load_persona(persona)
        self.chat_history = []
        
    def _format_docs(self, tools: List[Dict[str, Any]]) -> str:
        docs = []
        for t in tools:
            sig = t.get("signature", "") or ""
            capability = " [Self-Resolving]" if "sub_agent" in sig else ""
            docs.append(f"- {t.get('full_doc', t.get('name'))}{capability}")
        return "\n".join(docs)

    async def run(self, user_input: str) -> str:
        relevant_tools = await self.registry.get_relevant_tools(user_input)
        tool_docs = self._format_docs(relevant_tools)
        
        task_history = [f"User: {user_input}"]
        indent = "  " * self.depth

        # Combine Persona with the Base Protocol
        system_prompt = f"{self.persona_text}\n\n{BASE_PROTOCOL.format(tool_definitions=tool_docs)}"

        for i in range(8):
            full_context = self.chat_history + task_history
            prompt = (system_prompt + "\n\n" + "\n".join(full_context) + "\nThought:")
            
            response = self.client.models.generate_content(model=self.model_id, contents=prompt)
            raw_output = "Thought: " + response.text.strip()
            logger.debug(f"\n{indent}--- Step {i+1} (Depth {self.depth}) ---\n{indent}{raw_output}")
            
            if "Final Answer:" in raw_output:
                final_answer = raw_output.split("Final Answer:")[-1].strip()
                if self.depth == 0:
                    self.chat_history.append(f"User: {user_input}")
                    self.chat_history.append(f"Assistant: {final_answer}")
                return final_answer
            
            try:
                action_match = re.search(r"Action:\s*(\w+)", raw_output)
                input_match = re.search(r"Action Input:\s*({.*})", raw_output, re.DOTALL)
                
                if not action_match or not input_match:
                    raise ValueError("Incomplete Action/Action Input format.")
                
                action_name = action_match.group(1).strip()
                action_args = json.loads(input_match.group(1).strip())
                
                observation = await self.execute_func(action_name, action_args)
                
                task_history.append(raw_output)
                task_history.append(f"Observation: {observation}")
                logger.debug(f"{indent}Observation: {observation}")
                
            except Exception as e:
                obs = f"Error: {str(e)}"
                task_history.append(raw_output)
                task_history.append(f"Observation: {obs}")
                logger.error(f"{indent}Execution Error: {obs}")

        return "Max reasoning steps reached."
