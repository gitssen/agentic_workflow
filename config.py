import os
from google import genai
from dotenv import load_dotenv

# Load .env file at the start
load_dotenv()

_GENAI_CLIENT = None

def get_genai_client() -> genai.Client:
    """Returns a singleton instance of the genai Client."""
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set in .env")
        _GENAI_CLIENT = genai.Client(api_key=api_key)
    return _GENAI_CLIENT

MODEL_ID = "gemini-2.5-flash"
EMBEDDING_MODEL_ID = "models/gemini-embedding-001"
FIRESTORE_DATABASE_ID = os.environ.get("FIRESTORE_DATABASE_ID", "default")
