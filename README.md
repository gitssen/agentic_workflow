# LangGraph-Powered MCP Agentic Workflow

A state-of-the-art AI agent framework built on **LangGraph** and the **Model Context Protocol (MCP)**. This system features **Tool-RAG** (Retrieval-Augmented Generation for tools), **Recursive Sub-Agents**, a formal **State Machine** architecture, and a deep **Music Curation & Control** integration.

---

## 🏗 Architecture Overview

The system utilizes a decoupled, modern architecture that separates reasoning, orchestration, and execution, now enhanced with cross-language scripts and hybrid communication protocols.

### 1. The Reasoning Engine (LangGraph Multi-Agent)
The core logic utilizes a formal **LangGraph StateGraph** featuring a **Supervisor + Specialists** architecture.
- **Supervisor Routing**: A Chief QA Supervisor evaluates the shared `artifact` and intelligently delegates to specialists.
- **Dynamic Personas**: Supports runtime selection of expert personas (e.g., `music_curator`, `senior_coder`, `news_analyst`, `travel_companion`) stored as Markdown templates in `agent/prompts/`.
- **Blackboard State**: Agents collaborate via a universal `artifact` in the graph state, ensuring high-quality, iterative output.
- **Context Isolation**: Strictly manages conversation history to prevent LLM "loops" and ensure specialists focus on the current task state.

### 2. The MCP Host & Backend (`backend/main.py`)
The "Brain" connects the reasoning engine to execution environments and the web.
- **Hybrid Protocol Support**: A custom FastAPI bridge supporting both **JSON** and **Protobuf** via automated content negotiation (Accept/Content-Type headers).
- **Tool-RAG**: Uses Gemini embeddings and Firestore Vector Search to dynamically inject context-relevant tools into the agent's prompt.
- **SSE Streaming**: Provides real-time "Thought-Action-Observation" updates to the frontend via Server-Sent Events.

### 3. The Music & Media Ecosystem
A specialized suite for high-performance music management and smart playback.
- **Sonos Integration**: Native discovery and control of Sonos speakers (Play, Pause, Volume, Seek, Status).
- **Automated Curation**: The `music_curator` persona generates structured JSON playlists based on natural language prompts.
- **Rich Metadata & Art**:
    - **Go Ingestion**: High-performance Go scripts for scanning and indexing thousands of tracks.
    - **Smart Art Fetching**: Multi-tier art resolution (Embedded Metadata -> Local SQLite Cache -> Firestore -> MusicBrainz/CoverArtArchive).
    - **Local Streaming**: Serves audio and embedded art directly from the filesystem to Sonos or the Web UI.

### 4. The MCP Server (`agent/mcp_server.py`)
The "Hands" of the operation. It manages the execution of Python functions.
- **Self-Resolving Tools**: Automatically injects a `SubAgent` into tools, allowing them to gather missing context recursively.
- **Execution Isolation**: Tools run in a separate process, protecting the main reasoning engine from side effects.

---

## 🛠 Project Structure

- `agent/`: The core agent logic and MCP host.
  - `prompts/`: Markdown templates for different agent personas.
  - `tools/`: Vanilla Python functions for Search, Coding, Traffic, News, and Music.
  - `agent_logic.py`: The **LangGraph** definition and `SubAgent` implementation.
  - `mcp_server.py`: The tool execution server.
- `api_proto/`: Protobuf definitions for cross-platform type safety.
- `backend/main.py`: FastAPI bridge with Sonos control and audio streaming.
- `frontend/`: Next.js web interface with real-time reasoning visualization and a custom Music Player.
- `scripts/`: High-performance **Go** scripts for music library management (`ingest_music`, `check_art`).
- `music_cache.db`: Local SQLite database for fast album art caching.

---

## 🚀 Getting Started

### Prerequisites
1. **Gemini API Key**: Get one from [Google AI Studio](https://aistudio.google.com/).
2. **Firebase Project**: A Firestore database with a **Vector Index** on the `embedding` field in the `tools` and `songs` collections.
3. **Python 3.13+**, **Go 1.22+**, and **Node.js 20+**.

### Installation
1. Clone the repository.
2. Setup the virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   ./.venv/bin/pip install -r requirements.txt
   cd frontend && npm install && cd ..
   ```

### Configuration
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_key_here
GOOGLE_PROJECT_ID=your_project_id_here
FIRESTORE_DATABASE_ID=default
# Optional API Keys for Tools
GOOGLE_MAPS_API_KEY=...
NEWS_API_KEY=...
```

---

## 🏃 Running the System

### 1. Music Library Ingestion (Optional)
If you have a local music library, index it for the agent:
```bash
# Set your music path in scripts/ingest_music.go or pass as arg
go run scripts/ingest_music.go /path/to/my/music
```

### 2. Register Tools
Updates the Firestore index with latest signatures and embeddings:
```bash
export PYTHONPATH=$(pwd)
./.venv/bin/python3 agent/register_tools.py
```

### 3. Start the Full Stack
The provided script starts the FastAPI backend (port 8000), MCP Server, and Next.js frontend (port 3000):
```bash
chmod +x start.sh
./start.sh
```

---

## 📜 Design Principles

1. **Protocol Negotiation**: Support modern (Protobuf) and web-standard (JSON) communication seamlessly.
2. **Recursive Reasoning**: Tools can think for themselves by spinning up sub-agents.
3. **Hybrid Performance**: Combine the reasoning power of Python with the execution speed of Go.
4. **Clean Context**: Use Tool-RAG to keep the LLM's attention focused on the most relevant capabilities.

---

## 🔍 Monitoring & Documentation
- **Logs**: Detailed reasoning traces are available in `logs/agent.log`.
- **Design Docs**: See `design.md` for architectural deep-dives and `MULTI_SERVER_PLAN.md` for the future roadmap.
