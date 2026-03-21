import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from google import genai
from dotenv import load_dotenv

# Load .env file at the start
load_dotenv()

# --- Logging Configuration ---
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "agent.log")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

def setup_logger(name: str):
    """Sets up a logger with a RotatingFileHandler (DEBUG) and a StreamHandler (sys.stderr)."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG) # Catch everything at the logger level
    
    # Prevent duplicate handlers if logger is already set up
    if not logger.handlers:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)

        # Rotating File Handler (Captures everything: DEBUG, INFO, WARNING, ERROR)
        file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1*1024*1024, backupCount=3)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        
        # Stream Handler (Captures only INFO and above for a clean CLI)
        # We explicitly use sys.stderr to avoid corrupting MCP Stdio (stdout)
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(logging.Formatter("%(message)s"))
        
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
    
    return logger

# Global logger for config/system tasks
logger = setup_logger("System")

_GENAI_CLIENT = None

def get_genai_client() -> genai.Client:
    """Returns a singleton instance of the genai Client."""
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY environment variable not set in .env")
            raise ValueError("GEMINI_API_KEY environment variable not set in .env")
        _GENAI_CLIENT = genai.Client(api_key=api_key)
    return _GENAI_CLIENT

MODEL_ID = "gemini-2.5-flash"
EMBEDDING_MODEL_ID = "models/gemini-embedding-001"
FIRESTORE_DATABASE_ID = os.environ.get("FIRESTORE_DATABASE_ID", "default")
