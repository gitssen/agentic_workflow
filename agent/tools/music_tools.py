import json
import random
from typing import List, Dict, Any
from agent.config import get_genai_client, EMBEDDING_MODEL_ID, EMBEDDING_DIM, FIRESTORE_DATABASE_ID, setup_logger
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
            config={
                "output_dimensionality": EMBEDDING_DIM,
                "task_type": "RETRIEVAL_QUERY"
            }
        )
        query_vector = embedding_response.embeddings[0].values
        
        # 1. First, try an exact/keyword search for the artist or title
        # This helps when the user asks for a specific name that vector search might blur
        keyword_songs = []
        words = mood_description.split()
        if len(words) < 4: # Only do keyword search for short, specific queries
            for word in words:
                if len(word) < 3: continue
                # Search by artist (case-insensitive-ish via range)
                artist_matches = collection.where("artist", ">=", word.capitalize()).where("artist", "<=", word.capitalize() + "\uf8ff").limit(limit).get()
                for doc in artist_matches:
                    d = doc.to_dict()
                    d.pop("embedding", None)
                    d["id"] = doc.id
                    if d["id"] not in [s["id"] for s in keyword_songs]:
                        keyword_songs.append(d)
        
        # 2. Perform native vector search
        fetch_limit = max(limit * 3, 30)
        results = collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=fetch_limit
        ).get()
        
        vector_songs = []
        for doc in results:
            data = doc.to_dict()
            data.pop("embedding", None)
            data["id"] = doc.id
            vector_songs.append(data)
            
        # 3. Merge: Prioritize keyword matches, then add vector results
        keyword_ids = [s["id"] for s in keyword_songs]
        all_songs = keyword_songs + [s for s in vector_songs if s["id"] not in keyword_ids]
        
        if not all_songs:
            return json.dumps({"status": "error", "message": "No songs found in the database."})
            
        # Shuffle a bit of the vector results but keep specific matches high
        songs = all_songs[:limit]
        return json.dumps({"status": "success", "songs": songs}, indent=2)
        
    except Exception as e:
        logger.error(f"Error querying song database: {e}")
        return json.dumps({"status": "error", "message": str(e)})
