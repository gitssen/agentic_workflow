# MCP-Native Recursive Agentic Workflow

An advanced, production-ready AI agent framework built on the **Model Context Protocol (MCP)**. This system features **Tool-RAG** (Retrieval-Augmented Generation for tools) using Firestore Vector Search and **Recursive Sub-Agents** for autonomous, self-healing tool execution.

---

## 🏗 Architecture Overview

The system follows a decoupled Client-Server architecture, ensuring that tool execution is isolated from reasoning logic.

### 1. The MCP Host (`main.py`)
The "Brain" of the operation. It acts as an MCP Client that connects to the tool server.
- **Tool-RAG**: Uses Gemini embeddings to find only the most relevant tools for a given query, reducing context window clutter and costs.
- **ReAct Loop**: Orchestrates the Reasoning-Acting cycle.
- **MCP Bridge**: Communicates with the server via standardized Stdio JSON-RPC.

### 2. The MCP Server (`mcp_server.py`)
The "Hands" of the operation. It manages the tool execution environment.
- **Protocol Wrapper**: Translates vanilla Python functions into standardized MCP Tool definitions.
- **Recursive Injection**: Automatically injects a `SubAgent` into tools that require it, enabling tools to solve their own sub-tasks.
- **Isolation**: Runs in its own process, ensuring stability and portability.

### 3. Smart Tool Discovery (`agent_logic.py`)
- **Sub-Agents**: Tools can ask a sub-agent to find missing information (e.g., location for weather) using natural language, rather than hardcoding dependencies.
- **Indented Logging**: Nested reasoning steps are indented in the logs for easy traceability of "stitching."

---

## 🛠 Project Structure

- `agent/tools/`: **Vanilla Python** functions. Easy to test, portable to any framework.
- `agent/cli_host.py`: The MCP Host/Agent loop (CLI version).
- `agent/mcp_server.py`: The MCP Server process.
- `agent/agent_logic.py`: Shared ReAct reasoning logic.
- `agent/register_tools.py`: Tool registry manager.
- `backend/main.py`: FastAPI server that bridges the Frontend to the Agent logic.
- `frontend/`: Next.js web interface for the agent.

---

## 🚀 Getting Started

### Prerequisites
1. **Gemini API Key**: Get one from [Google AI Studio](https://aistudio.google.com/).
2. **Firebase Project**: A Firestore database named `default` with a **Vector Index** on the `embedding` field in the `tools` collection (Dimension: 768, Measure: COSINE).
3. **Python 3.13+**
4. **Node.js & npm** (for the frontend)

### Installation
1. Clone the repository.
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   cd frontend && npm install && cd ..
   ```

### Configuration
Create a `.env` file in the root directory (see `.env.placeholder` for a full list):
```env
GEMINI_API_KEY=your_key_here
GOOGLE_PROJECT_ID=your_project_id_here
GOOGLE_MAPS_API_KEY=your_maps_api_key_here
UBER_API_KEY=your_uber_key_here
RAINFOREST_API_KEY=your_rainforest_key_here
FIRESTORE_DATABASE_ID=default

# Optional: Only needed if not authenticated via gcloud CLI
# GOOGLE_APPLICATION_CREDENTIALS=path/to/serviceAccountKey.json
```

---

## 🏃 Running the System

### 1. Register Tools (Required once or after tool changes)
Run the registry script to upload tool metadata and embeddings to Firestore:
```bash
PYTHONPATH=agent ./venv/bin/python3 agent/register_tools.py
```

### 2. Start the Agent CLI (Direct Access)
To interact with the agent directly in your terminal:
```bash
PYTHONPATH=agent ./venv/bin/python3 agent/cli_host.py
```

### 3. Start the Web Application (Full Stack)

The easiest way to start both the Backend and Frontend is using the provided `start.sh` script:
```bash
chmod +x start.sh
./start.sh
```

Alternatively, you can start them manually:

**Start the Backend:**
```bash
PYTHONPATH=agent ./venv/bin/python3 backend/main.py
```

**Start the Frontend:**
```bash
cd frontend && npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Development Mode (Auto-Reload)
To automatically reload the agent CLI and re-register tools on change:
```bash
PYTHONPATH=agent ./venv/bin/python3 agent/cli_dev.py
```

---

## 🧩 Adding New Tools

To expand the agent's capabilities:
1. Create a new `.py` file in the `tools/` directory.
2. Define a documented function. 
3. (Optional) Add a `sub_agent` parameter if the tool needs to perform recursive discovery.
4. Run `register_tools.py`.

**Example:**
```python
def get_user_bio(username: str):
    """Fetches user biography from the database."""
    # Logic here...
```

---

## 📜 Design Principles

1. **Protocol First**: Use MCP to ensure tools are universally compatible with any AI client.
2. **Vanilla Tools**: Keep tool logic pure Python. Avoid locking tools into specific agentic frameworks.
3. **Lazy Discovery**: Don't flood the LLM with 50 tools. Use Tool-RAG to retrieve only the 3-5 most relevant ones.
4. **Autonomous Resolution**: Let "Smart Tools" fix their own missing data via Sub-Agents. This makes the system "Self-Healing."

---

## 🔍 Troubleshooting
Check `logs/agent.log` for a detailed trace of the ReAct reasoning loop, including any internal Sub-Agent calls.
