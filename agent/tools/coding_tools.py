import io
import contextlib
import traceback
from agent.config import setup_logger

logger = setup_logger("Tool:Coding")

def execute_python_code(code: str) -> str:
    """
    Executes Python code and returns the standard output or error traceback.
    Useful for testing snippets or solving algorithmic problems.
    
    Args:
        code: The Python code to execute.
    """
    logger.debug("  [Tool] Executing Python code...")
    
    # Simple safety check (not meant to be fully secure, just to catch obvious bad things in a mock environment)
    if "import os" in code or "import sys" in code or "subprocess" in code:
        return "Error: For security reasons, OS/system level imports are blocked in this environment."
        
    output_capture = io.StringIO()
    
    try:
        with contextlib.redirect_stdout(output_capture):
            # We use an empty dictionary for locals/globals to prevent modifying the agent's environment
            exec(code, {})
        
        result = output_capture.getvalue()
        if not result.strip():
            return "Execution successful. No output produced."
        return result
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Python Execution Error:\n{error_traceback}")
        return f"Execution Error:\n{error_traceback}"
