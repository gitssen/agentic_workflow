# LangGraph-Powered MCP Agentic Workflow

A state-of-the-art AI agent framework built on **LangGraph** and the **Model Context Protocol (MCP)**. This system features **Tool-RAG** (Retrieval-Augmented Generation for tools), **Recursive Sub-Agents**, and a formal **State Machine** architecture for high reliability and scalability.

---

## 🏗 Architecture Overview

The system utilizes a decoupled, modern architecture that separates reasoning, orchestration, and execution.

### 1. The Reasoning Engine (LangGraph)
The core logic has been evolved from a manual ReAct loop into a formal **LangGraph StateGraph**.
- **State Machine**: Orchestrates the conversation flow using nodes (`agent`, `tools`) and conditional edges (`should_continue`).
- **Persistence Readiness**: The graph structure is designed to support checkpointing and long-running stateful sessions.
- **Native Tool Binding**: Leverages Gemini's function-calling capabilities through LangChain's `bind_tools` for maximum precision.

### 2. The MCP Host (`backend/main.py`)
The "Brain" that connects to specialized execution environments.
- **Tool-RAG**: Uses Gemini embeddings and Firestore Vector Search to dynamically inject only context-relevant tools into the agent's prompt.
- **SSE Streaming**: Provides real-time "Thought-Action-Observation" updates to the frontend via Server-Sent Events.
- **Standardized Communication**: Uses the Model Context Protocol to talk to the tool server via Stdio.

### 3. The MCP Server (`agent/mcp_server.py`)
The "Hands" of the operation. It manages the execution of Python functions.
- **Dynamic Schema Generation**: Automatically translates Python functions into strict JSON Schemas using Pydantic, ensuring 100% compatibility with Gemini.
- **Self-Resolving Tools**: Automatically injects a `SubAgent` into tools, allowing them to gather missing context (e.g., location) autonomously.
- **Execution Isolation**: Tools run in a separate process, protecting the main reasoning engine from execution errors.

---

## 🛠 Project Structure

- `agent/`: The core package.
  - `tools/`: **Vanilla Python** functions. Documented and portable.
  - `agent_logic.py`: The **LangGraph** definition and `SubAgent` implementation.
  - `mcp_server.py`: The tool execution server.
  - `register_tools.py`: Management script for Firestore tool indexing.
  - `config.py`: Centralized logging and client initialization.
- `backend/main.py`: FastAPI bridge between the Agent and the Web.
- `frontend/`: Next.js web interface featuring real-time reasoning visualization.
- `start.sh`: Unified startup script for the entire stack.

---

## 🚀 Getting Started

### Prerequisites
1. **Gemini API Key**: Get one from [Google AI Studio](https://aistudio.google.com/).
2. **Firebase Project**: A Firestore database with a **Vector Index** on the `embedding` field in the `tools` collection (Dimension: 768, Measure: COSINE).
3. **Python 3.13+**
4. **Node.js & npm**

### Installation
1. Clone the repository.
2. Setup the virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # or use ./.venv/bin/python3
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   cd frontend && npm install && cd ..
   ```

### Configuration
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_key_here
GOOGLE_PROJECT_ID=your_project_id_here
GOOGLE_MAPS_API_KEY=your_maps_api_key_here
UBER_API_KEY=your_uber_key_here
RAINFOREST_API_KEY=your_rainforest_key_here
FIRESTORE_DATABASE_ID=default
```

---

## 🏃 Running the System

### 1. Register Tools (Required after tool changes)
Updates the Firestore index with latest signatures and embeddings:
```bash
export PYTHONPATH=$(pwd)
./.venv/bin/python3 agent/register_tools.py
```

### 2. Start the Full Stack
The provided script starts the FastAPI backend, MCP Server, and Next.js frontend:
```bash
chmod +x start.sh
./start.sh
```

### 3. Verify the Installation
Run the end-to-end verification script to test connectivity and tool reasoning:
```bash
./.venv/bin/python3 verify_system.py
```

---

## 📜 Design Principles

1. **Graph-Based Orchestration**: Move beyond loops to state machines for complex multi-agent workflows.
2. **Dynamic Schemas**: Trust-but-verify tool arguments using Pydantic models generated at runtime.
3. **Tool-RAG**: Keep the context window clean by only showing the agent what it needs to see.
4. **Absolute Package Structure**: Standardized imports (`from agent.config ...`) for robustness across different entry points.

---

## 🔍 Monitoring
Detailed traces of the reasoning process, tool calls, and Sub-Agent interactions are available in `logs/agent.log`.
