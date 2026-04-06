# Engineering Guidelines: Embedding & Vector Search

## 1. Centralized Configuration
All models and embedding parameters MUST be read from environment variables via `agent/config.py`. 
- **MODEL_ID**: The primary Gemini model for generation (e.g., `gemini-2.5-flash`).
- **EMBEDDING_MODEL_ID**: The model used for vector generation (e.g., `models/gemini-embedding-001`).
- **EMBEDDING_DIM**: The output dimensionality for all embeddings.

## 2. Firestore Vector Search Constraints
Firestore has a strict limit of **2048 dimensions** for native `Vector` objects and vector indexes. 
- **Standard**: We use **768** dimensions for all embeddings (Tools, Music, etc.) to ensure compatibility and performance.
- **NEVER** use the default 3072 dimensions for `gemini-embedding-001` when storing as a native Vector.

## 3. Embedding Consistency
When generating embeddings for search or indexing, always pass the `output_dimensionality` explicitly:
- **Python**: `config={"output_dimensionality": EMBEDDING_DIM}`
- **Go**: `emModel.OutputDimensionality = &dim` (where `dim` is parsed from `EMBEDDING_DIM`)

## 4. Anti-Hallucination Protocol
Specialists (like `music_curator`) MUST NOT invent data. 
- Always verify tool results before presenting them in an `<artifact>`.
- The Supervisor MUST have access to raw tool outputs to perform truthfulness verification.
- If a search returns no results, the agent MUST report the lack of matches rather than using placeholders.

## 5. Multi-Language Alignment
- Both Python (`agent/tools/music_tools.py`) and Go (`scripts/ingest_music.go`) must use the same `.env` constants.
- Go indexing scripts MUST use `firestore.Vector` type (not `[]float64`) for the embedding field to ensure Firestore creates a vector index compatible with Python queries.
