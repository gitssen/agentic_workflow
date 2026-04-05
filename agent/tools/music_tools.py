import json
from typing import List, Dict, Any
from agent.config import get_genai_client, EMBEDDING_MODEL_ID, FIRESTORE_DATABASE_ID, setup_logger
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

logger = setup_logger("MusicTools")

if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

def query_song_database(mood_description: str, limit: int = 10) -> str:
    """
    Searches the local song database to find songs matching a specific mood or vibe description.
    
    Args:
        mood_description: A natural language description of the desired music (e.g., 'upbeat workout music with high energy', 'cozy rainy day acoustic').
        limit: The maximum number of songs to return (default 10).
    
    Returns:
        A JSON string containing the list of matching songs with their metadata.
    """
    logger.info(f"Querying song database for mood: '{mood_description}' (limit {limit})")
    try:
        client = get_genai_client()
        collection = db.collection("songs")
        
        # Generate embedding for the search query
        embedding_response = client.models.embed_content(
            model=EMBEDDING_MODEL_ID,
            contents=mood_description,
            config={"output_dimensionality": 768}
        )
        query_vector = embedding_response.embeddings[0].values
        
        # Perform vector search
        results = collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=limit
        ).get()
        
        songs = []
        for doc in results:
            data = doc.to_dict()
            # Remove embedding from output to save context space
            data.pop("embedding", None)
            songs.append(data)
            
        if not songs:
            return json.dumps({"status": "error", "message": "No songs found in the database."})
            
        return json.dumps({"status": "success", "songs": songs}, indent=2)
        
    except Exception as e:
        logger.error(f"Error querying song database: {e}")
        return json.dumps({"status": "error", "message": str(e)})
