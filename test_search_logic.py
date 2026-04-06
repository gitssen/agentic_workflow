import os
import sys
from dotenv import load_dotenv

# Ensure the project root is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.config import FIRESTORE_DATABASE_ID, setup_logger
import firebase_admin
from firebase_admin import firestore

load_dotenv()
logger = setup_logger("SearchTester")

if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

def test_search(search_term):
    print(f"\n--- Testing search for: '{search_term}' ---")
    collection = db.collection("songs")
    
    # 1. Test case-sensitive prefix
    print(f"1. Testing Case-Sensitive Prefix ('{search_term}')...")
    res = collection.where("title", ">=", search_term).where("title", "<=", search_term + "\uf8ff").limit(5).get()
    print(f"   Found: {len(res)} matches")
    for doc in res:
        d = doc.to_dict()
        print(f"   - {d.get('title')} by {d.get('artist')}")

    # 2. Test lowercase prefix (if field exists)
    search_lower = search_term.lower()
    print(f"2. Testing Lowercase Prefix ('{search_lower}')...")
    res = collection.where("title_lowercase", ">=", search_lower).where("title_lowercase", "<=", search_lower + "\uf8ff").limit(5).get()
    print(f"   Found: {len(res)} matches")
    for doc in res:
        d = doc.to_dict()
        print(f"   - {d.get('title')} by {d.get('artist')}")

    # 3. Sample check: What fields actually exist?
    print("\n3. Inspecting a sample document...")
    sample = collection.limit(1).get()
    if sample:
        d = sample[0].to_dict()
        print(f"   Fields available: {list(d.keys())}")
        print(f"   Sample Title: {d.get('title')}")
        print(f"   Sample Title Lowercase: {d.get('title_lowercase')}")
    else:
        print("   No documents found in 'songs' collection.")

if __name__ == "__main__":
    search_val = sys.argv[1] if len(sys.argv) > 1 else "A"
    test_search(search_val)
