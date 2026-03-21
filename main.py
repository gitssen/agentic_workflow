import os
import json
import re
import inspect
import importlib.util
from typing import List, Dict, Any
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import firestore

# Load environment variables
load_dotenv()

from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from config import get_genai_client, MODEL_ID, EMBEDDING_MODEL_ID, FIRESTORE_DATABASE_ID

# --- 1. Firebase Initialization ---
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

# --- 2. The Tool Registry (Semantic Search) ---

class ToolRegistry:
    def __init__(self, collection_name: str = "tools"):
        self.collection = db.collection(collection_name)
        self.client = get_genai_client()
        self._local_tools = self._load_local_tools()

    def _load_local_tools(self) -> Dict[str, Any]:
        local_tools = {}
        tools_dir = "tools"
        if not os.path.exists(tools_dir):
            return local_tools
            
        for filename in os.listdir(tools_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                file_path = os.path.join(tools_dir, filename)
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                for name, obj in inspect.getmembers(module):
                    if inspect.isfunction(obj) and obj.__module__ == module_name:
                        local_tools[name] = obj
        return local_tools

    def get_relevant_tools(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        embedding_response = self.client.models.embed_content(
            model=EMBEDDING_MODEL_ID,
            contents=query,
            config={"output_dimensionality": 768}
        )
        query_vector = embedding_response.embeddings[0].values
        
        results = self.collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=limit
        ).get()
        
        relevant_tools = []
        for doc in results:
            tool_data = doc.to_dict()
            if tool_data["name"] in self._local_tools:
                tool_data["func"] = self._local_tools[tool_data["name"]]
                relevant_tools.append(tool_data)
        
        return relevant_tools

# --- 3. The Brain (Generic ReAct Agent) ---

SYSTEM_PROMPT_TEMPLATE = """
You are a helpful AI assistant. You solve problems by following a structured ReAct (Reasoning and Acting) loop.
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
4. Always check if you have actually answered the User's specific question before giving the Final Answer.
"""

class GenericReActAgent:
    def __init__(self, registry: ToolRegistry, model_id: str = MODEL_ID):
        self.client = get_genai_client()
        self.model_id = model_id
        self.registry = registry
        self.chat_history = [] # Long-term User/Assistant exchanges
        
    def _format_docs(self, tools: List[Dict[str, Any]]) -> str:
        docs = []
        for t in tools:
            docs.append(f"- {t['full_doc']}")
        return "\n".join(docs)

    def run(self, user_input: str):
        # Step 1: Semantic Search for relevant tools
        relevant_tools = self.registry.get_relevant_tools(user_input)
        tool_docs = self._format_docs(relevant_tools)
        print(f"tools found: {[t['name'] for t in relevant_tools]}")
        available_tool_funcs = {t['name']: t['func'] for t in relevant_tools}

        # Step 2: Initialize local task history for this specific ReAct loop
        task_history = [f"User: {user_input}"]

        for i in range(8):
            # Combine long-term chat history with current task's intermediate steps
            full_context = self.chat_history + task_history
            prompt = (SYSTEM_PROMPT_TEMPLATE.format(tool_definitions=tool_docs) + 
                      "\n\n" + "\n".join(full_context) + "\nThought:")
            
            response = self.client.models.generate_content(model=self.model_id, contents=prompt)
            raw_output = "Thought: " + response.text.strip()
            print(f"\n--- Step {i+1} ---\n{raw_output}")
            
            if "Final Answer:" in raw_output:
                final_answer = raw_output.split("Final Answer:")[-1].strip()
                # Update long-term history with just the clean exchange
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
                
                if action_name in available_tool_funcs:
                    observation = str(available_tool_funcs[action_name](**action_args))
                else:
                    observation = f"Error: Tool '{action_name}' not available for this task."
                
                task_history.append(raw_output)
                task_history.append(f"Observation: {observation}")
                print(f"Observation: {observation}")
                
            except Exception as e:
                obs = f"Error parsing/executing tool: {str(e)}. Check your format."
                task_history.append(raw_output)
                task_history.append(f"Observation: {obs}")
                print(f"Observation: {obs}")

        return "Max reasoning steps reached."

# --- 4. Execution ---

def main():
    try:
        registry = ToolRegistry()
        agent = GenericReActAgent(registry=registry)
        print("--- Generic ReAct Agent (with Firebase Tool-RAG) Ready ---")
    except ValueError as e:
        print(f"Error: {e}")
        return

    while True:
        try:
            query = input("\nUser > ").strip()
            if query.lower() in ["exit", "quit"]: break
            if query: print(f"\nResult > {agent.run(query)}")
        except KeyboardInterrupt: break
        except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    main()
