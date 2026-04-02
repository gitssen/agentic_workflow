# Project Design & Architecture: Agentic Workflow Workspace

This document provides a detailed technical overview of the hierarchical multi-agent system implemented in this repository.

## 1. Architectural Philosophy: The "Supervisor-Specialist" Pattern

The core of this project is built on a **Hierarchical Multi-Agent System (HMAS)** using **LangGraph**. Unlike a linear chain or a single "do-it-all" agent, this architecture separates the **Reasoning/Quality Control** from the **Execution/Drafting**.

### Key Reasoning Decisions:
*   **Why LangGraph?** We chose LangGraph because it allows for **cyclic graphs** and **state persistence**. Traditional LLM chains are linear; agentic workflows require the ability to loop back (e.g., from Specialist to Supervisor for feedback).
*   **The "Blackboard" (Artifact) Pattern:** We use a shared `artifact` field in the state. Instead of agents passing complex objects to each other, they all "write" to a shared blackboard. This allows the Supervisor to evaluate the *work product* itself rather than the agent's internal thought process.
*   **Separation of Concerns:** By using specialized personas (`blog_writer`, `style_editor`, etc.), we reduce the "distraction" an LLM faces. A specialist only sees instructions relevant to its task, leading to higher-quality output.
*   **MCP (Model Context Protocol):** We use MCP to decouple the **Agent Logic** from the **Tool Execution**. This allows the tools to run in their own isolated environment (the MCP Server) while the Agent (the MCP Host) simply calls them via a standardized JSON interface.

---

## 2. System Diagram (Conceptual)

```text
[ User Query ] 
      |
      v
[ Supervisor Node ] <-----------+
      |                         |
      | (Decision: Specialist)   | (Feedback Loop)
      v                         |
[ Specialist Node ] ------------+
      |
      | (Decision: Needs Tool)
      v
[ MCP Tool Executor ]
      |
      | (Tool Result)
      v
[ Specialist Node ] (Refines Artifact)
```

---

## 3. File-by-File Detailed Documentation

### 3.1 Agent Core (`/agent`)

*   **`agent_logic.py`**: The "Heart" of the system.
    *   Defines `AgentState`: The shared memory (messages, tools, artifact, feedback).
    *   `supervisor_node`: Uses a structured LLM call to decide if the task is done or which specialist to call next.
    *   `call_specialist`: Dynamically loads a persona, manages conversation history isolation (to prevent loops), and handles artifact extraction using `<artifact>` tags.
    *   `execute_tools`: The bridge that calls the actual MCP tools.
    *   **Decision:** We use `astream_events` (v2) to provide a rich, real-time "Thought Stream" to the frontend.

*   **`config.py`**: System-wide configuration.
    *   Manages `GEMINI_API_KEY` and initializes the Google GenAI SDK.
    *   Configures a dual-target logger (Rotating File for debug, Stderr for clean CLI info).
    *   Defines the `MODEL_ID` (Gemini 2.5 Flash).

*   **`mcp_server.py`**: The Tool Execution Environment.
    *   Exposes local Python functions as MCP Tools.
    *   **Decision:** It injects a `SubAgent` capability into tools. This allows a tool (like a "researcher") to actually spin up its *own* recursive agent to solve a sub-problem.

*   **`register_tools.py`**: The Tool-RAG Indexer.
    *   Scans the `/tools` directory.
    *   Generates embeddings for every function's docstring using `gemini-embedding-001`.
    *   Stores metadata in **Firestore**. This allows the agent to perform "Vector Search" to find the right tool among hundreds without hitting context limits.

### 3.2 Personas & Prompts (`/agent/prompts`)

*   **`supervisor.md`**: The QA Lead. Focused on constraints, style, and final approval.
*   **`blog_writer.md`**: The Researcher. Explicitly told to ignore style and focus on raw facts.
*   **`style_editor.md`**: The Stylist. Focused on prose, tone, and authorial voice.
*   **`senior_coder.md` / `qa_tester.md`**: Specialized for Python development and verification.

### 3.3 Infrastructure & Backend

*   **`backend/main.py`**: The FastAPI Bridge.
    *   Manages the persistent connection to the MCP Server.
    *   Provides the `/chat` endpoint which transforms the LangGraph event stream into a Server-Sent Events (SSE) stream for the UI.

*   **`agent/tools/`**: Individual capability modules.
    *   `search.py`: Google Search grounding via Gemini.
    *   `coding_tools.py`: Filesystem and code execution capabilities.
    *   `weather.py`, `traffic.py`, etc.: External API integrations.

*   **`start.sh`**: The Orchestrator.
    *   Cleans up old processes.
    *   Starts the Backend with `uvicorn --reload` for hot-reloading.
    *   Starts the Frontend Next.js dev server.

### 3.4 Frontend (`/frontend`)

*   **`Chat.tsx`**: The main interface.
    *   Consumes the SSE stream from the backend.
    *   Parses "Thoughts", "Actions", "Observations", and "Final Answers" into distinct UI components.
    *   **Decision:** Uses `react-markdown` and `prism` for high-quality rendering of agent-generated code and formatted text.

---

## 4. Key Implementation Details

### Context Isolation & Loop Prevention
One of the most critical fixes was **isolating specialist context**. LLMs often get "stuck" if they see too much history. In `agent_logic.py`, we now:
1.  Clear previous specialist history when a new one starts.
2.  Pass only the original user request + current draft + supervisor feedback.
3.  This forces the specialist to act on the *current state* rather than repeating what the previous agent said.

### Turn-Order Compliance
Gemini models require a strict `Human -> AI -> Human -> AI` turn order. Our `supervisor_node` was updated to ensure that every evaluation request ends with a `HumanMessage`, preventing `INVALID_ARGUMENT` errors when specialists produce multiple internal turns.
