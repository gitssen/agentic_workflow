#!/bin/bash

# Aggressively kill any existing processes
echo "🧹 Cleaning up existing processes..."
lsof -ti :8000 | xargs kill -9 2>/dev/null
lsof -ti :3000 | xargs kill -9 2>/dev/null
lsof -ti :3001 | xargs kill -9 2>/dev/null

# Make sure all children of old runs are dead
pkill -f "mcp_server.py"
pkill -f "next-dev"

echo "🚀 Starting Agentic Workflow..."

# Start Backend (FastAPI + MCP Host) with Auto-Reload
# The backend will automatically start the MCP Server subprocess
echo "Starting Backend (FastAPI) with --reload..."
export PYTHONPATH=$(pwd)
# We use uvicorn with --reload for hot-reloading on Python file changes
./.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

sleep 2


# Start Frontend (Next.js)
echo "Starting Frontend (Next.js)..."
cd frontend && npm run dev -- -H 0.0.0.0 &
FRONTEND_PID=$!

echo "--------------------------------------------------------"
echo "Backend: http://192.168.1.100:8000"
echo "Frontend: http://192.168.1.100:3000"
echo "--------------------------------------------------------"
echo "Press Ctrl+C to stop all services."

# Handle shutdown
trap "kill $BACKEND_PID $FRONTEND_PID; pkill -f mcp_server.py; exit" INT TERM
wait
