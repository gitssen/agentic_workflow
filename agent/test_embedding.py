import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

embedding_response = client.models.embed_content(
    model="models/gemini-embedding-001",
    contents="test"
)
embedding = embedding_response.embeddings[0].values
print(f"Embedding length: {len(embedding)}")
