import firebase_admin
from firebase_admin import firestore
from agent.config import FIRESTORE_DATABASE_ID

if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

docs = db.collection('songs').limit(1).get()
if not docs:
    print("No documents found in 'songs' collection.")
else:
    data = docs[0].to_dict()
    emb = data.get('embedding')
    print(f"Embedding type: {type(emb)}")
    if emb:
        # Check if it's a list or a Vector object
        print(f"Is list: {isinstance(emb, list)}")
        try:
            from google.cloud.firestore_v1.vector import Vector
            print(f"Is Vector: {isinstance(emb, Vector)}")
        except ImportError:
            print("Could not import Vector for check.")
        
        if isinstance(emb, list):
            print(f"Length: {len(emb)}")
            print(f"First 5: {emb[:5]}")
