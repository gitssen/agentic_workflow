import os
import sys
import asyncio
import socket
import html
import urllib.parse
import soco
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

# --- Protobuf Imports ---
from api_proto import api_pb2
from google.protobuf import json_format

from fastapi import Request, Response as FAResponse
from functools import wraps

# Initialize FastAPI and Logger
app = FastAPI(title="Agentic Workflow Bridge")
logger = setup_logger("Backend")

# --- Protobuf Utilities ---
class ProtobufResponse(FAResponse):
    media_type = "application/x-protobuf"
    def render(self, content: Any) -> bytes:
        if isinstance(content, bytes):
            return content
        if hasattr(content, "SerializeToString"):
            return content.SerializeToString()
        return super().render(content)

def protobuf_endpoint(pb_request_type: Any = None, pb_response_type: Any = None):
    """
    Decorator for FastAPI endpoints to support both JSON and Protobuf via negotiation.
    - If Accept is application/x-protobuf, returns Protobuf.
    - If Content-Type is application/x-protobuf, parses body as Protobuf.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 1. Identify Request and Check Negotiation
            request: Request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                # Try to find in kwargs if not in args
                request = kwargs.get("request")
            
            # 2. Check Input Content-Type for Protobuf
            is_pb_request = False
            if request and request.headers.get("Content-Type") == "application/x-protobuf" and pb_request_type:
                body = await request.body()
                pb_msg = pb_request_type()
                pb_msg.ParseFromString(body)
                # Convert PB to Dict/Pydantic-like if needed or pass as is
                # For now, we'll pass the PB message object
                kwargs["pb_data"] = pb_msg
                is_pb_request = True

            # 3. Call the actual function
            result = await func(*args, **kwargs)

            # 4. Check Output Negotiation
            if request and "application/x-protobuf" in request.headers.get("Accept", ""):
                if pb_response_type:
                    # If result is already the PB message, just return it
                    if isinstance(result, pb_response_type):
                        return ProtobufResponse(result)
                    
                    # Otherwise, try to map dict/object to PB message
                    pb_res = pb_response_type()
                    if isinstance(result, dict):
                        # Use json_format to map dict to proto (handles camelCase/snake_case etc)
                        try:
                            json_format.ParseDict(result, pb_res, ignore_unknown_fields=True)
                            return ProtobufResponse(pb_res)
                        except Exception as e:
                            logger.error(f"Protobuf mapping failed: {e}")
                            logger.error(f"Dict content: {result}")
                            raise HTTPException(status_code=500, detail=f"Protobuf mapping error: {str(e)}")
                
            return result
        return wrapper
    return decorator

# CORS Configuration for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Content-Type"],
)

import time

# --- Global Music State ---
class GlobalMusicState(BaseModel):
    current_song: Optional[Dict[str, Any]] = None
    is_playing: bool = False
    playlist: List[Dict[str, Any]] = []
    last_updated: float = 0

global_music_state = GlobalMusicState()

@app.get("/music/state")
async def get_music_state():
    """Returns the current global music playback state."""
    return global_music_state

@app.post("/music/state")
async def update_music_state(state: GlobalMusicState):
    """Updates the global music playback state."""
    global global_music_state
    global_music_state = state
    # Use real-world Unix time so frontend Date.now() can compare it
    global_music_state.last_updated = time.time()
    return {"status": "success"}

# --- Sonos Client Management ---
class MCPManager:
    """Manages a persistent connection to the MCP Server."""
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._exit_stack = None
        self._client_gen = None

    async def connect(self):
        try:
            mcp_path = os.path.join(os.path.dirname(__file__), "..", "agent", "mcp_server.py")
            logger.info(f"Starting MCP Server from: {mcp_path}")
            server_params = StdioServerParameters(
                command="./.venv/bin/python3",
                args=[mcp_path],
                env={**os.environ}
            )
            
            async def _do_connect():
                self._client_gen = stdio_client(server_params)
                read, write = await self._client_gen.__aenter__()
                self.session = ClientSession(read, write)
                await self.session.__aenter__()
                await self.session.initialize()
                
            await asyncio.wait_for(_do_connect(), timeout=15.0)
            logger.info("Connected to MCP Server")
        except Exception as e:
            logger.error(f"Failed to connect to MCP Server: {e}")
            self.session = None

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
        from agent.config import get_genai_client, EMBEDDING_MODEL_ID, EMBEDDING_DIM
        client = get_genai_client()
        embedding_response = client.models.embed_content(
            model=EMBEDDING_MODEL_ID, contents=query, config={"output_dimensionality": EMBEDDING_DIM}
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

class SonosPlayRequest(BaseModel):
    ip: str
    song_id: str

class SonosControlRequest(BaseModel):
    ip: str
    action: str # "pause", "resume", "stop", "volume"
    value: Optional[int] = None

def get_local_ip():
    """Helper to get the local network IP of the server for Sonos to reach."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # use a public IP to find the primary interface IP
        s.connect(('8.8.8.8', 80))
        IP = s.getsockname()[0]
    except Exception:
        IP = '192.168.1.100'
    finally:
        s.close()
    return IP

@app.get("/sonos/devices")
async def list_sonos_devices():
    """Discovers Sonos devices on the local network."""
    try:
        # Use discovery from multiple methods if possible, or just standard soco.discover
        devices = soco.discover(timeout=5)
        if not devices:
            # Fallback attempt
            await asyncio.sleep(1)
            devices = soco.discover(timeout=5)
            
        if not devices:
            return []
        return [{"name": d.player_name, "ip": d.ip_address} for d in devices]
    except Exception as e:
        logger.error(f"Sonos discovery failed: {e}")
        return []

@app.post("/sonos/play")
async def play_on_sonos(request: SonosPlayRequest):
    """Commands a Sonos speaker to play a specific song ID with proper metadata."""
    try:
        device = soco.SoCo(request.ip)
        if device.group and device.group.coordinator:
            device = device.group.coordinator
            
        doc = await asyncio.to_thread(db.collection("songs").document(request.song_id).get)
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Song not found")
        
        song_data = doc.to_dict()
        title = html.escape(song_data.get("title", "Unknown"))
        artist = html.escape(song_data.get("artist", "Unknown"))
        
        # Determine media type from extension
        filepath = song_data.get("filepath", "")
        mime = "audio/mpeg"
        if filepath.lower().endswith(".flac"): mime = "audio/flac"
        elif filepath.lower().endswith(".wav"): mime = "audio/wav"
        elif filepath.lower().endswith(".m4a") or filepath.lower().endswith(".mp4"): mime = "audio/mp4"

        local_ip = get_local_ip()
        # Ensure song_id is properly quoted for the URL
        safe_song_id = urllib.parse.quote(request.song_id)
        stream_url = f"http://{local_ip}:8000/stream/{safe_song_id}"
        
        # Metadata that works well as a 'radio station' / stream
        metadata = (
            '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" '
            'xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">'
            '<item id="-1" parentID="-1" restricted="1">'
            f'<dc:title>{title}</dc:title>'
            f'<upnp:artist>{artist}</upnp:artist>'
            f'<upnp:class>object.item.audioItem.musicTrack</upnp:class>'
            f'<res protocolInfo="http-get:*:{mime}:*">{stream_url}</res>'
            '</item></DIDL-Lite>'
        )

        logger.info(f"Casting to Sonos ({device.player_name} @ {device.ip_address}): {stream_url}")
        
        # Clear state
        try:
            device.stop()
            await asyncio.sleep(0.5)
        except:
            pass

        # Use play_uri with force_radio=True as it's often more resilient for local server streams
        try:
            device.play_uri(stream_url, meta=metadata, force_radio=True)
            # Some devices set URI but stay PAUSED
            await asyncio.sleep(1)
            device.play()
        except Exception as e:
            logger.warning(f"play_uri (radio) failed, trying standard: {e}")
            device.play_uri(stream_url, meta=metadata, force_radio=False)
            await asyncio.sleep(1)
            device.play()

        return {"status": "success", "device": device.player_name}
    except Exception as e:
        logger.error(f"Sonos playback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sonos/status/{ip}")
async def get_sonos_status(ip: str):
    """Gets current playback status from a Sonos device."""
    try:
        device = soco.SoCo(ip)
        if device.group and device.group.coordinator:
            device = device.group.coordinator
            
        transport_info = device.get_current_transport_info()
        track_info = device.get_current_track_info()
        
        # Helper to convert HH:MM:SS to seconds
        def to_seconds(time_str):
            if not time_str or ":" not in time_str: return 0
            parts = time_str.split(':')
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            return 0

        return {
            "state": transport_info.get("current_transport_state"),
            "position": to_seconds(track_info.get("position")),
            "duration": to_seconds(track_info.get("duration")),
            "volume": device.volume
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/sonos/control")
async def control_sonos(request: SonosControlRequest):
    """Controls playback (pause, resume, stop, volume) on a Sonos device."""
    try:
        device = soco.SoCo(request.ip)
        if device.group and device.group.coordinator:
            device = device.group.coordinator

        if request.action == "pause":
            device.pause()
        elif request.action == "resume":
            device.play()
        elif request.action == "stop":
            device.stop()
        elif request.action == "volume":
            if request.value is not None:
                device.volume = request.value
        elif request.action == "seek":
            if request.value is not None:
                # Convert seconds to HH:MM:SS
                m, s = divmod(int(request.value), 60)
                h, m = divmod(m, 60)
                seek_str = f"{h:02d}:{m:02d}:{s:02d}"
                try:
                    device.seek(seek_str)
                except Exception as seek_e:
                    logger.warning(f"Seek failed (likely radio mode): {seek_e}")
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
            
        return {"status": "success", "device": device.player_name, "action": request.action}
    except Exception as e:
        logger.error(f"Sonos control failed ({request.action}): {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/playlists", response_model=None)
@protobuf_endpoint(api_pb2.PlaylistSaveRequest, api_pb2.PlaylistSaveResponse)
async def save_playlist(request: Request, pb_data: Any = None):
    """Saves a curated playlist to Firestore."""
    try:
        if pb_data:
            # Convert protobuf to dict for Firestore
            data_dict = json_format.MessageToDict(pb_data, preserving_proto_field_name=True)
            name = data_dict.get("name")
            prompt = data_dict.get("prompt")
            songs = data_dict.get("songs", [])
        else:
            data = await request.json()
            name = data.get("name")
            prompt = data.get("prompt")
            songs = data.get("songs", [])

        new_ref = db.collection("playlists").document()
        playlist_data = {
            "id": new_ref.id,
            "name": name,
            "prompt": prompt,
            "songs": songs,
            "created_at": firestore.SERVER_TIMESTAMP
        }
        new_ref.set(playlist_data)
        return {"status": "success", "playlist_id": new_ref.id}
    except Exception as e:
        logger.error(f"Failed to save playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/playlists", response_model=None)
@protobuf_endpoint(None, api_pb2.ListPlaylistsResponse)
async def list_playlists(request: Request):
    """Returns all saved playlists."""
    try:
        docs = db.collection("playlists").order_by("created_at", direction=firestore.Query.DESCENDING).get()
        playlists = []
        for doc in docs:
            d = doc.to_dict()
            # Convert Firestore timestamp to Unix timestamp (int64) for Protobuf
            if "created_at" in d and hasattr(d["created_at"], "timestamp"):
                d["created_at"] = int(d["created_at"].timestamp())
            elif "created_at" in d and d["created_at"] is None:
                d["created_at"] = 0
            playlists.append(d)
        return {"playlists": playlists}
    except Exception as e:
        logger.error(f"Failed to list playlists: {e}")
        return {"playlists": []}

@app.get("/songs", response_model=None)
@protobuf_endpoint(None, api_pb2.ListSongsResponse)
async def list_songs(request: Request, search: str = None, limit: int = 100, last_id: str = None):
    """Returns a list of all indexed songs with optional search filtering and cursor pagination."""
    try:
        collection = db.collection("songs")
        songs = []
        
        if search:
            search_clean = search.strip().lower()
            # 1. Try title_lowercase prefix search (Fastest)
            query = collection.where("title_lowercase", ">=", search_clean).where("title_lowercase", "<=", search_clean + "\uf8ff").limit(limit)
            results = query.get()
            
            # 2. Try artist_lowercase prefix search
            if not results:
                query = collection.where("artist_lowercase", ">=", search_clean).where("artist_lowercase", "<=", search_clean + "\uf8ff").limit(limit)
                results = query.get()

            # 3. FINAL FALLBACK: Substring search (Memory Intensive but better UX for small libraries)
            if not results:
                all_docs = collection.stream()
                for doc in all_docs:
                    d = doc.to_dict()
                    title = d.get("title_lowercase", "").lower()
                    artist = d.get("artist_lowercase", "").lower()
                    if search_clean in title or search_clean in artist:
                        d.pop("embedding", None)
                        songs.append(d)
                        if len(songs) >= limit:
                            break
                return {"songs": songs}
            else:
                for doc in results:
                    d = doc.to_dict()
                    d.pop("embedding", None)
                    d["album_art_url"] = f"http://192.168.1.100:8000/art/{d['id']}"
                    songs.append(d)
        else:
            # Standard pagination by title
            query = collection.order_by("title").limit(limit)
            if last_id:
                last_doc = collection.document(last_id).get()
                if last_doc.exists:
                    query = query.start_after(last_doc)
            results = query.get()
            for doc in results:
                d = doc.to_dict()
                d.pop("embedding", None)
                d["album_art_url"] = f"http://192.168.1.100:8000/art/{d['id']}"
                songs.append(d)
        
        return {"songs": songs}
    except Exception as e:
        logger.error(f"Failed to list songs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ChatResponse(BaseModel):
    response: str
    thought: Optional[str] = None

# --- Endpoints ---
@app.get("/personas", response_model=None)
@protobuf_endpoint(None, api_pb2.GetPersonasResponse)
async def get_personas(request: Request):
    """Lists available personas from the agent/prompts directory."""
    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "agent", "prompts")
    if not os.path.exists(prompts_dir):
        logger.warning(f"Prompts directory not found: {prompts_dir}")
        return {"personas": ["general"]}
    personas = [f[:-3] for f in os.listdir(prompts_dir) if f.endswith(".md")]
    logger.info(f"Returning personas: {personas}")
    return {"personas": personas}

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

@app.post("/curate_playlist", response_model=None)
@protobuf_endpoint(api_pb2.CuratePlaylistRequest, api_pb2.CuratePlaylistResponse)
async def curate_playlist(request: Request, pb_data: Any = None):
    """Uses the HMAS to generate a curated playlist based on a natural language prompt."""
    if not mcp_manager.session:
        raise HTTPException(status_code=503, detail="MCP Server not connected")

    prompt = ""
    if pb_data:
        prompt = pb_data.prompt
    else:
        # Fallback to JSON model
        try:
            json_body = await request.json()
            prompt = json_body.get("prompt", "")
        except:
            raise HTTPException(status_code=400, detail="Invalid request body")

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
    strict_prompt = prompt + "\n\nCRITICAL: You MUST use the query_song_database tool to find songs based on this context. Your final output MUST be wrapped in <artifact> tags and formatted strictly as a JSON array of song objects. DO NOT escape single quotes (e.g. use ' instead of \\') as it is invalid JSON."
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
        # Pre-process common LLM JSON errors: backslash-escaped single quotes
        # Standard JSON does not support \' and it often causes parsing errors
        processed_json = playlist_json.replace(r"\'", "'")
        try:
            raw_playlist = json.loads(processed_json)
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
                    
                    # Use local art endpoint
                    song_data["album_art_url"] = f"http://192.168.1.100:8000/art/{song_id}"
                    song_data.pop("embedding", None)
                    enriched_songs.append(song_data)
                else:
                    # If not in DB, use provided info but ensure a title and art link exist
                    if not item.get("title") and item.get("filepath"):
                        item["title"] = os.path.basename(item["filepath"]).rsplit('.', 1)[0]
                    item["album_art_url"] = f"http://192.168.1.100:8000/art/{song_id}"
                    enriched_songs.append(item)
            
            logger.info(f"Successfully curated {len(enriched_songs)} songs.")
            return {"status": "success", "playlist": enriched_songs}
        except json.JSONDecodeError:
            logger.error(f"Failed to parse playlist JSON: {processed_json}")
            raise HTTPException(status_code=500, detail="Agent returned invalid playlist JSON.")
    else:
        logger.error(f"Agent failed to return an artifact. Output: {final_output}")
        raise HTTPException(status_code=500, detail="Agent failed to generate a playlist artifact.")

@app.get("/art/{song_id}")
async def get_art(song_id: str):
    """Extracts and serves embedded album art from a song file."""
    doc_ref = db.collection("songs").document(song_id)
    doc = await asyncio.to_thread(doc_ref.get)
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Song not found")
    
    filepath = doc.to_dict().get("filepath")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    import io
    from mutagen import File
    
    try:
        audio = File(filepath)
        if audio is None:
            raise HTTPException(status_code=404, detail="Could not parse audio file")
            
        art_data = None
        mime = "image/jpeg"
        
        if filepath.lower().endswith(".mp3"):
            if hasattr(audio, 'tags') and audio.tags and 'APIC:' in audio.tags:
                art_data = audio.tags['APIC:'].data
                mime = audio.tags['APIC:'].mime
            elif hasattr(audio, 'tags') and audio.tags:
                # Fallback to search any APIC tag
                for tag in audio.tags.values():
                    if hasattr(tag, 'type') and tag.type == 3: # Front cover
                        art_data = tag.data
                        mime = tag.mime
                        break
        elif filepath.lower().endswith(".flac"):
            if hasattr(audio, 'pictures') and audio.pictures:
                art_data = audio.pictures[0].data
                mime = audio.pictures[0].mime
        elif filepath.lower().endswith((".m4a", ".mp4")):
            if audio is not None and 'covr' in audio:
                art_data = audio['covr'][0]
                # mutagen.mp4 doesn't give mime directly but covr is usually jpeg/png
                mime = "image/jpeg" 
        
        if art_data:
            return StreamingResponse(io.BytesIO(art_data), media_type=mime)
            
    except Exception as e:
        logger.error(f"Failed to extract art: {e}")

    # Fallback to a placeholder or 404
    raise HTTPException(status_code=404, detail="No embedded art found")

@app.get("/stream/{song_id}")
async def stream_audio(song_id: str):
    """Streams a local audio file by looking up its filepath in Firestore."""
    doc_ref = db.collection("songs").document(song_id)
    doc = await asyncio.to_thread(doc_ref.get)
    
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
        
    file_size = os.path.getsize(filepath)
    logger.info(f"SONOS/STREAM: {song_id} -> {filepath} ({media_type}, {file_size} bytes)")
    
    return FileResponse(
        filepath, 
        media_type=media_type, 
        headers={
            "Accept-Ranges": "bytes",
        }
    )

@app.get("/metadata/{song_id}")
async def get_metadata(song_id: str):
    """Fetches rich metadata for a song from Firestore."""
    doc_ref = db.collection("songs").document(song_id)
    doc = await asyncio.to_thread(doc_ref.get)
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Song not found.")
        
    data = doc.to_dict()
    data.pop("embedding", None) # Remove raw embedding vector
    
    return {"status": "success", "metadata": data}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
