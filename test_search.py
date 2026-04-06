import os
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from dotenv import load_dotenv
from google import genai

load_dotenv()

from agent.config import get_genai_client, EMBEDDING_MODEL_ID, EMBEDDING_DIM, FIRESTORE_DATABASE_ID
client = get_genai_client()

# Setup Firestore
database_id = FIRESTORE_DATABASE_ID

if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client(database_id=database_id)

def test_search(query_text):
    print(f"Testing search for: '{query_text}'")
    
    # 1. Generate embedding
    res = client.models.embed_content(
        model=EMBEDDING_MODEL_ID,
        contents=query_text,
        config={"output_dimensionality": EMBEDDING_DIM}
    )
    query_vector = res.embeddings[0].values
    print(f"Query vector generated (len: {len(query_vector)})")

    # 2. Query Firestore
    collection = db.collection("songs")
    results = collection.find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_vector),
        distance_measure=DistanceMeasure.COSINE,
        limit=5
    ).get()

    print(f"Found {len(list(results))} results:")
    for doc in results:
        data = doc.to_dict()
        # Calculate distance if possible (not directly in snapshots, but let's see metadata)
        print(f"- {data.get('title')} (ID: {doc.id})")
        print(f"  Description: {data.get('description_for_search')[:100]}...")

if __name__ == "__main__":
    test_search("experimental Bengali rock")
    print("\n" + "="*50 + "\n")
    test_search("lo-fi chill music")
