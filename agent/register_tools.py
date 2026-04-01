import os
import sys
import inspect
import importlib.util
import hashlib
from dotenv import load_dotenv

# Ensure the project root is in sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()

from google.cloud.firestore_v1.vector import Vector
from agent.config import get_genai_client, EMBEDDING_MODEL_ID, FIRESTORE_DATABASE_ID, setup_logger

# Initialize logger for registry script
logger = setup_logger("Registry")

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

def get_tool_hash(func):
    """Generates a SHA-256 hash of the tool's source code."""
    source = inspect.getsource(func)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()

def register_tool(func, collection_name="tools"):
    """Generates embedding and stores tool metadata in Firestore only if changed."""
    client = get_genai_client()
    collection = db.collection(collection_name)
    
    name = func.__name__
    current_hash = get_tool_hash(func)
    
    # Check if tool already exists and has the same hash
    doc_ref = collection.document(name)
    doc = doc_ref.get()
    
    if doc.exists:
        existing_data = doc.to_dict()
        if existing_data.get("hash") == current_hash:
            logger.debug(f"  [Registry] Tool '{name}' is up to date. Skipping.")
            return

    sig_obj = inspect.signature(func)
    properties = {}
    required = []
    for p_name, p in sig_obj.parameters.items():
        if p_name == "sub_agent":
            continue
        p_type = "string"
        if p.annotation == int: p_type = "integer"
        elif p.annotation == float: p_type = "number"
        elif p.annotation == bool: p_type = "boolean"
        properties[p_name] = {"type": p_type}
        if p.default == inspect.Parameter.empty:
            required.append(p_name)

    doc_str = func.__doc__.strip() if func.__doc__ else "No description available."
    full_description = f"{name}{str(sig_obj)}: {doc_str}"
    
    logger.info(f"  [Registry] Registering/Updating tool: {name} (New Hash: {current_hash[:8]}...)")
    
    # Generate embedding
    embedding_response = client.models.embed_content(
        model=EMBEDDING_MODEL_ID,
        contents=full_description,
        config={
            "output_dimensionality": 768
        }
    )
    embedding = embedding_response.embeddings[0].values
    
    # Store in Firestore
    doc_ref.set({
        "name": name,
        "signature": str(sig_obj),
        "properties": properties,
        "required": required,
        "description": doc_str,
        "full_doc": full_description,
        "embedding": Vector(embedding),
        "hash": current_hash
    })

def main():
    # Use the tools directory within the same folder as this script
    tools_dir = os.path.join(os.path.dirname(__file__), "tools")
    if not os.path.exists(tools_dir):
        logger.error(f"Error: {tools_dir} directory not found.")
        return

    for filename in os.listdir(tools_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = filename[:-3]
            file_path = os.path.join(tools_dir, filename)
            
            # Import the module dynamically
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find all functions in the module
            for name, obj in inspect.getmembers(module):
                if (inspect.isfunction(obj) or inspect.iscoroutinefunction(obj)) and obj.__module__ == module_name:
                    register_tool(obj)

if __name__ == "__main__":
    main()
