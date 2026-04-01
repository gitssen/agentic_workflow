# Plan: Native Multi-Server MCP Integration

## Objective
To evolve the existing Agentic Workflow into a native Multi-Server architecture. The host will connect to multiple MCP servers simultaneously (e.g., the local Python server and an external Media server), aggregate their tools via Tool-RAG, and route executions to the correct server.

---

## 1. Industry Standard Comparison
How commercial AI clients like **Claude Desktop** and **Gemini** handle Multi-Server MCP:

*   **Configuration & Aggregation:** They use a configuration file (like `mcp.json`) defining an array of servers. On startup, the host process spawns parallel connections to *each* server, calls `list_tools()` on all of them, and aggregates the results into a single toolset.
*   **Routing:** The LLM sees a flat list of tools. When it calls a specific tool, the Host intercepts the call, identifies the source server, and routes the JSON-RPC request to that specific connection.
*   **Sub-Agents:** Standard clients *do not* use recursive injection. If a tool needs data, it returns an error/request to the main LLM. Our system's unique value is the injected `SubAgent`, which solves sub-tasks recursively without polluting the main context window.

---

## 2. Proposed Architecture: Multi-Server Host
We will modify the "Brain" (`agent/cli_host.py` and `backend/main.py`) to manage a pool of MCP connections.

### Key Components to Update
1.  **Configuration (`servers_config.json`):** A new JSON file to define external servers (command, args, env vars).
2.  **Dynamic Tool Registry (`agent/register_tools.py`):**
    *   **Old way:** Parsed local `.py` files.
    *   **New way:** Must loop through `servers_config.json`, initialize MCP client sessions, call `list_tools()`, and generate embeddings for the returned JSON schemas. Each tool in Firestore will need a `server_id` attribute.
3.  **The Host Router (`agent/cli_host.py` & `agent_logic.py`):**
    *   `cli_host.py` will establish persistent connections to all configured servers.
    *   `agent_logic.py`'s `execute_func` will route the JSON-RPC call to the correct session based on the tool's `server_id`.

---

## 3. The "Sub-Agent" Complication & Solution

### The Challenge
Our `SubAgent` feature uses Python-specific injection. Inside `agent/mcp_server.py`, we inject a live Python object into the tool function. Because external servers (Node.js/Go) communicate over standard JSON-RPC, we **cannot** pass a live Python object to them.

### The Solution: "Local-Only Recursion" (Recommended)
*   **Local Python Tools:** Continue to receive the `sub_agent` injection for "Self-Healing" capabilities.
*   **External Tools (e.g., Media):** Treated as standard "leaf nodes" (atomic functions). The reasoning loop happens *before* or *after* calling the external tool. This aligns perfectly with how Claude/Gemini handle external MCP servers while preserving our unique recursive advantage for local logic.

---

## 4. Phased Implementation Plan

### Phase 1: Configuration & Connection Pool
*   Create `servers_config.json`.
*   Update `agent/cli_host.py` to maintain a dictionary of `ClientSession` objects keyed by `server_id`.

### Phase 2: Registry & Tool-RAG Update
*   Modify `agent/register_tools.py` to fetch tools from all servers via `list_tools()`.
*   Generate and store embeddings in Firestore with the `server_id` metadata.

### Phase 3: Routing & Execution
*   Update `execute_via_mcp` in the host to lookup the `server_id` for the requested tool name.
*   Route the JSON-RPC `call_tool` request to the appropriate session.

---

## 5. Expected File Changes
*   `servers_config.json` (New)
*   `agent/cli_host.py` (Refactor for multi-session support)
*   `agent/register_tools.py` (Refactor to use MCP `list_tools`)
*   `agent/agent_logic.py` (Update `execute_func` routing)
*   `backend/main.py` (Sync with multi-server host changes)
