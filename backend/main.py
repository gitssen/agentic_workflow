import os
import sys
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Add the project root directory to the path so we can import 'agent' as a package
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from agent.agent_logic import GenericReActAgent, load_persona
from agent.config import setup_logger, FIRESTORE_DATABASE_ID

# Initialize FastAPI and Logger
app = FastAPI(title="Agentic Workflow Bridge")
logger = setup_logger("Backend")

# CORS Configuration for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Content-Type"],
)

# --- MCP Client Management ---
class MCPManager:
    """Manages a persistent connection to the MCP Server."""
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._exit_stack = None

    async def connect(self):
        mcp_path = os.path.join(os.path.dirname(__file__), "..", "agent", "mcp_server.py")
        logger.info(f"Starting MCP Server from: {mcp_path}")
        server_params = StdioServerParameters(
            command="./.venv/bin/python3",
            args=[mcp_path],
            env={**os.environ}
        )
        # Note: stdio_client is an async context manager. 
        # For a persistent backend, we use it to start the server.
        self._client_gen = stdio_client(server_params)
        read, write = await self._client_gen.__aenter__()
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()
        logger.info("Connected to MCP Server")

    async def disconnect(self):
        if self.session:
            await self.session.__aexit__(None, None, None)
        if self._client_gen:
            await self._client_gen.__aexit__(None, None, None)
        logger.info("Disconnected from MCP Server")

mcp_manager = MCPManager()

@app.on_event("startup")
async def startup_event():
    await mcp_manager.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await mcp_manager.disconnect()

# --- Registry for the Agent ---
# We reuse the Firestore-based registry from the agent package
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

class BackendRegistry:
    def __init__(self, collection_name: str = "tools"):
        self.collection = db.collection(collection_name)

    async def get_relevant_tools(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        from agent.config import get_genai_client, EMBEDDING_MODEL_ID
        client = get_genai_client()
        embedding_response = client.models.embed_content(
            model=EMBEDDING_MODEL_ID, contents=query, config={"output_dimensionality": 768}
        )
        query_vector = embedding_response.embeddings[0].values
        results = self.collection.find_nearest(
            vector_field="embedding", query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE, limit=limit
        ).get()
        return [doc.to_dict() for doc in results]

# --- API Models ---
class ChatRequest(BaseModel):
    message: str
    persona: str = "general"

class PlaylistRequest(BaseModel):
    prompt: str

class PlaylistSaveRequest(BaseModel):
    name: str
    prompt: str
    songs: List[Dict[str, Any]]

@app.post("/playlists")
async def save_playlist(request: PlaylistSaveRequest):
    """Saves a curated playlist to Firestore."""
    try:
        new_ref = db.collection("playlists").document()
        playlist_data = {
            "id": new_ref.id,
            "name": request.name,
            "prompt": request.prompt,
            "songs": request.songs,
            "created_at": firestore.SERVER_TIMESTAMP
        }
        new_ref.set(playlist_data)
        return {"status": "success", "playlist_id": new_ref.id}
    except Exception as e:
        logger.error(f"Failed to save playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/playlists")
async def list_playlists():
    """Returns all saved playlists."""
    try:
        docs = db.collection("playlists").order_by("created_at", direction=firestore.Query.DESCENDING).get()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Failed to list playlists: {e}")
        return []

class ChatResponse(BaseModel):
    response: str
    thought: Optional[str] = None

# --- Endpoints ---
@app.get("/personas")
async def get_personas():
    """Lists available personas from the agent/prompts directory."""
    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "agent", "prompts")
    if not os.path.exists(prompts_dir):
        logger.warning(f"Prompts directory not found: {prompts_dir}")
        return ["general"]
    personas = [f[:-3] for f in os.listdir(prompts_dir) if f.endswith(".md")]
    logger.info(f"Returning personas: {personas}")
    return personas

import json
import re
import httpx
import sqlite3

# --- Local Cache Setup (SQLite) ---
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "music_cache.db")

def init_local_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS album_art (
            cache_key TEXT PRIMARY KEY,
            art_url TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_local_db()

def clean_music_string(s: str) -> str:
    """Removes common parenthetical suffixes like (Live) or (scratchy) for better search."""
    if not s: return ""
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\[.*?\]", "", s)
    return s.strip()

def get_cached_art(artist: str, album: str, title: str) -> Optional[str]:
    key = f"{artist}|{album}|{title}".lower()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT art_url FROM album_art WHERE cache_key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def save_art_to_cache(artist: str, album: str, title: str, url: str):
    key = f"{artist}|{album}|{title}".lower()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO album_art (cache_key, art_url) VALUES (?, ?)", (key, url))
    conn.commit()
    conn.close()

# --- Album Art Service ---
async def get_album_art(artist: str, album: str, title: str = None, song_id: str = None) -> str:
    """Fetches album art from local cache, then Firestore, then MusicBrainz."""
    # 1. Check Local SQLite Cache First
    cached = get_cached_art(artist, album, title)
    if cached: return cached

    # 2. Check Firestore cache
    if song_id:
        doc_ref = db.collection("songs").document(song_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            if data.get("album_art_url"):
                save_art_to_cache(artist, album, title, data["album_art_url"])
                return data["album_art_url"]

    if not artist and not album and not title:
        return None

    c_artist = clean_music_string(artist)
    c_album = clean_music_string(album)
    c_title = clean_music_string(title)

    logger.info(f"Fetching album art for: {c_artist} - {c_album} (Title: {c_title})")
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            headers = {"User-Agent": "AgenticPlaylistCurator/1.1.0 ( contact@example.com )"}
            
            queries = []
            if c_artist and c_album:
                queries.append(f"release-group/?query=artist:\"{c_artist}\" AND releasegroup:\"{c_album}\"")
            if c_artist and c_title:
                queries.append(f"release-group/?query=artist:\"{c_artist}\" AND releasegroup:\"{c_title}\"")
            if c_album:
                queries.append(f"release-group/?query=releasegroup:\"{c_album}\"")
            if c_title:
                queries.append(f"release/?query=release:\"{c_title}\"")

            for query_path in queries:
                await asyncio.sleep(1.1)
                search_url = f"https://musicbrainz.org/ws/2/{query_path}&fmt=json"
                res = await client.get(search_url, headers=headers)
                
                if res.status_code == 503:
                    await asyncio.sleep(2.0)
                    continue
                if res.status_code != 200:
                    continue
                
                data = res.json()
                mbid = None
                is_release = "release/" in query_path
                if is_release:
                    releases = data.get("releases", [])
                    if releases: mbid = releases[0]["id"]
                else:
                    groups = data.get("release-groups", [])
                    if groups: mbid = groups[0]["id"]

                if mbid:
                    type_path = "release" if is_release else "release-group"
                    art_url = f"https://coverartarchive.org/{type_path}/{mbid}/front"
                    art_res = await client.head(art_url)
                    
                    if art_res.status_code == 200:
                        final_url = str(art_res.url)
                        # Save to both Firestore and Local Cache
                        if song_id:
                            db.collection("songs").document(song_id).update({"album_art_url": final_url})
                        save_art_to_cache(artist, album, title, final_url)
                        logger.info(f"Found art! {final_url}")
                        return final_url

    except Exception as e:
        logger.error(f"Failed to fetch album art: {e}")
    
    return None

@app.post("/chat")
async def chat(request: ChatRequest):
    """Sends a message to the agent and returns a stream of reasoning steps."""
    if not mcp_manager.session:
        raise HTTPException(status_code=503, detail="MCP Server not connected")

    async def execute_via_mcp(name, args):
        logger.debug(f"Executing MCP Tool: {name} with args: {args}")
        try:
            res = await mcp_manager.session.call_tool(name, args)
            return res.content[0].text
        except Exception as e:
            logger.error(f"MCP Tool Call Error ({name}): {e}")
            raise

    registry = BackendRegistry()
    agent = GenericReActAgent(registry, execute_via_mcp, persona=request.persona)
    
    async def event_generator():
        try:
            async for step in agent.run(request.message):
                # We yield each step as a JSON string for the frontend to parse
                yield f"data: {json.dumps(step)}\n\n"
        except Exception as e:
            logger.error(f"Agent Error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/curate_playlist")
async def curate_playlist(request: PlaylistRequest):
    """Uses the HMAS to generate a curated playlist based on a natural language prompt."""
    if not mcp_manager.session:
        raise HTTPException(status_code=503, detail="MCP Server not connected")

    async def execute_via_mcp(name, args):
        try:
            res = await mcp_manager.session.call_tool(name, args)
            return res.content[0].text
        except Exception as e:
            logger.error(f"MCP Tool Call Error ({name}): {e}")
            raise

    registry = BackendRegistry()
    agent = GenericReActAgent(registry, execute_via_mcp, persona="music_curator", strict_persona=True)
    
    # Append strict instruction to the prompt to guarantee JSON output
    strict_prompt = request.prompt + "\n\nCRITICAL: You MUST use the query_song_database tool to find songs based on this context. Your final output MUST be wrapped in <artifact> tags and formatted strictly as a JSON array of song objects, exactly as instructed in your persona."
    final_output = await agent.run_full(strict_prompt)
    logger.info(f"Agent raw output for curation: {final_output[:500]}...")
    
    playlist_json = None
    match = re.search(r"<artifact>(.*?)</artifact>", final_output, re.DOTALL)
    if match:
        playlist_json = match.group(1).strip()
    else:
        if final_output.strip().startswith("[") and final_output.strip().endswith("]"):
            playlist_json = final_output.strip()
    
    if playlist_json:
        try:
            raw_playlist = json.loads(playlist_json)
            # Support both a direct list or a dict containing a 'songs' list
            if isinstance(raw_playlist, dict) and "songs" in raw_playlist:
                raw_playlist = raw_playlist["songs"]
            
            if not isinstance(raw_playlist, list):
                logger.error(f"Playlist is not a list: {type(raw_playlist)}")
                raise ValueError("Agent did not return a list of songs.")

            enriched_songs = []
            for item in raw_playlist:
                song_id = item.get("id")
                if not song_id: continue
                
                doc = db.collection("songs").document(song_id).get()
                if doc.exists:
                    song_data = doc.to_dict()
                    # Ensure title fallback
                    if not song_data.get("title"):
                        song_data["title"] = song_id.replace("_mp3", "").replace("_flac", "").replace("_", " ")
                    
                    # Rate limiting: MusicBrainz allows 1 req/sec
                    await asyncio.sleep(1.1)
                    art_url = await get_album_art(
                        artist=song_data.get("artist"), 
                        album=song_data.get("album"), 
                        title=song_data.get("title"),
                        song_id=song_id
                    )
                    song_data["album_art_url"] = art_url
                    song_data.pop("embedding", None)
                    enriched_songs.append(song_data)
                else:
                    # If not in DB, use provided info but ensure a title exists
                    if not item.get("title") and item.get("filepath"):
                        item["title"] = os.path.basename(item["filepath"]).rsplit('.', 1)[0]
                    enriched_songs.append(item)
            
            logger.info(f"Successfully curated {len(enriched_songs)} songs.")
            return {"status": "success", "playlist": enriched_songs}
        except json.JSONDecodeError:
            logger.error(f"Failed to parse playlist JSON: {playlist_json}")
            raise HTTPException(status_code=500, detail="Agent returned invalid playlist JSON.")
    else:
        logger.error(f"Agent failed to return an artifact. Output: {final_output}")
        raise HTTPException(status_code=500, detail="Agent failed to generate a playlist artifact.")

@app.get("/stream/{song_id}")
async def stream_audio(song_id: str):
    """Streams a local audio file by looking up its filepath in Firestore."""
    doc_ref = db.collection("songs").document(song_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        logger.error(f"Stream requested for unknown song ID: {song_id}")
        raise HTTPException(status_code=404, detail="Song not found in database.")
        
    data = doc.to_dict()
    filepath = data.get("filepath")
    
    if not filepath or not os.path.exists(filepath):
        logger.error(f"Audio file not found on disk: {filepath}")
        raise HTTPException(status_code=404, detail="Audio file not found on disk.")
    
    # Determine media type from extension
    media_type = "audio/mpeg"
    if filepath.lower().endswith(".flac"):
        media_type = "audio/flac"
    elif filepath.lower().endswith(".wav"):
        media_type = "audio/wav"
    elif filepath.lower().endswith(".m4a") or filepath.lower().endswith(".mp4"):
        media_type = "audio/mp4"
        
    logger.info(f"Streaming {filepath} as {media_type}")
    return FileResponse(
        filepath, 
        media_type=media_type, 
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        }
    )

@app.get("/metadata/{song_id}")
async def get_metadata(song_id: str):
    """Fetches rich metadata for a song from Firestore."""
    doc_ref = db.collection("songs").document(song_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Song not found.")
        
    data = doc.to_dict()
    data.pop("embedding", None) # Remove raw embedding vector
    
    return {"status": "success", "metadata": data}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
