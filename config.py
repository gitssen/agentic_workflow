import os
import logging
from logging.handlers import RotatingFileHandler
from google import genai
from dotenv import load_dotenv

# Load .env file at the start
load_dotenv()

# --- Logging Configuration ---
LOG_FILE = os.path.join("logs", "agent.log")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO

def setup_logger(name: str):
    """Sets up a logger with a RotatingFileHandler and a StreamHandler."""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    
    # Prevent duplicate handlers if logger is already set up
    if not logger.handlers:
        # Rotating File Handler (1MB per file, keep 3 backups)
        file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1*1024*1024, backupCount=3)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        
        # Stream Handler (for console output)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("%(message)s")) # Keep console clean
        
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
