import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

from agent.config import get_genai_client, EMBEDDING_MODEL_ID, EMBEDDING_DIM
client = get_genai_client()

embedding_response = client.models.embed_content(
    model=EMBEDDING_MODEL_ID,
    contents="test",
    config={"output_dimensionality": EMBEDDING_DIM}
)
embedding = embedding_response.embeddings[0].values
print(f"Embedding length: {len(embedding)}")
