import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.vector import Vector
from agent.config import FIRESTORE_DATABASE_ID

if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

def migrate():
    print(f"Starting migration for collection 'songs' in database '{FIRESTORE_DATABASE_ID}'...")
    collection = db.collection("songs")
    docs = collection.get()
    
    count = 0
    for doc in docs:
        data = doc.to_dict()
        emb = data.get("embedding")
        
        if isinstance(emb, list):
            # Truncate to 768 or pad if needed (should be 3072 based on inspection)
            new_emb = emb[:768]
            if len(new_emb) < 768:
                new_emb.extend([0.0] * (768 - len(new_emb)))
            
            # Update with proper Vector type
            doc.reference.update({
                "embedding": Vector(new_emb)
            })
            count += 1
            if count % 10 == 0:
                print(f"Migrated {count} songs...")
    
    print(f"Migration complete. Total songs updated: {count}")

if __name__ == "__main__":
    migrate()
