import os
import sys
from dotenv import load_dotenv

# Ensure the project root is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.config import FIRESTORE_DATABASE_ID, setup_logger
import firebase_admin
from firebase_admin import firestore

load_dotenv()
logger = setup_logger("Migration")

if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

def migrate():
    print(f"--- Starting Migration on Database: {FIRESTORE_DATABASE_ID} ---")
    collection = db.collection("songs")
    docs = collection.stream()
    
    count = 0
    batch = db.batch()
    
    for doc in docs:
        d = doc.to_dict()
        updates = {}
        
        if 'title' in d and 'title_lowercase' not in d:
            updates['title_lowercase'] = d['title'].lower()
        if 'artist' in d and 'artist_lowercase' not in d:
            updates['artist_lowercase'] = d['artist'].lower()
            
        if updates:
            batch.update(doc.reference, updates)
            count += 1
            
            # Commit in batches of 500
            if count % 500 == 0:
                batch.commit()
                print(f"Migrated {count} documents...")
                batch = db.batch()
                
    if count % 500 != 0:
        batch.commit()
        
    print(f"✨ Finished! Total migrated: {count}")

if __name__ == "__main__":
    migrate()
