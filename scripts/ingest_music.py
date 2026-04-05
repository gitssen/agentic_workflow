import os
import sys
import json
import librosa
import numpy as np
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from dotenv import load_dotenv

# Ensure the project root is in sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agent.config import get_genai_client, EMBEDDING_MODEL_ID, FIRESTORE_DATABASE_ID, setup_logger
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.vector import Vector

# Load environment variables
load_dotenv()

logger = setup_logger("MusicIngestion")

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client(database_id=FIRESTORE_DATABASE_ID)

def extract_metadata(filepath):
    """Extracts basic ID3/Vorbis tags."""
    metadata = {
        "title": os.path.basename(filepath),
        "artist": "Unknown Artist",
        "album": "Unknown Album",
        "genre": "Unknown Genre"
    }
    
    try:
        if filepath.lower().endswith('.mp3'):
            audio = MP3(filepath)
            if audio.tags:
                metadata["title"] = str(audio.tags.get('TIT2', [metadata["title"]])[0])
                metadata["artist"] = str(audio.tags.get('TPE1', [metadata["artist"]])[0])
                metadata["album"] = str(audio.tags.get('TALB', [metadata["album"]])[0])
                metadata["genre"] = str(audio.tags.get('TCON', [metadata["genre"]])[0])
        elif filepath.lower().endswith('.flac'):
            audio = FLAC(filepath)
            metadata["title"] = audio.get('title', [metadata["title"]])[0]
            metadata["artist"] = audio.get('artist', [metadata["artist"]])[0]
            metadata["album"] = audio.get('album', [metadata["album"]])[0]
            metadata["genre"] = audio.get('genre', [metadata["genre"]])[0]
    except Exception as e:
        logger.warning(f"Failed to extract metadata for {filepath}: {e}")
        
    return metadata

def extract_audio_features(filepath):
    """Extracts low-level audio features using Librosa."""
    logger.info(f"Analyzing audio: {filepath}")
    try:
        # Load audio (limit duration to save time, e.g., first 60 seconds)
        y, sr = librosa.load(filepath, duration=60.0)
        
        # Tempo
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)
        
        # Spectral Centroid (brightness)
        cent = librosa.feature.spectral_centroid(y=y, sr=sr)
        avg_cent = np.mean(cent)
        
        # RMSE (energy/loudness)
        rmse = librosa.feature.rms(y=y)
        avg_rmse = np.mean(rmse)
        
        # Zero Crossing Rate (percussiveness)
        zcr = librosa.feature.zero_crossing_rate(y)
        avg_zcr = np.mean(zcr)
        
        return {
            "tempo_bpm": float(tempo[0] if isinstance(tempo, (list, np.ndarray)) else tempo),
            "spectral_centroid": float(avg_cent),
            "energy_rmse": float(avg_rmse),
            "zero_crossing_rate": float(avg_zcr)
        }
    except Exception as e:
        logger.error(f"Failed to extract features for {filepath}: {e}")
        return None

def process_directory(directory_path):
    """Iterates through music files, extracts data, generates embeddings, and saves to Firestore."""
    client = get_genai_client()
    collection = db.collection("songs")
    
    supported_formats = ('.mp3', '.flac', '.wav')
    
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith(supported_formats):
                filepath = os.path.join(root, file)
                logger.info(f"Processing: {filepath}")
                
                metadata = extract_metadata(filepath)
                features = extract_audio_features(filepath)
                
                if not features:
                    continue
                
                # Construct a rich text description to embed
                description = (
                    f"Title: {metadata['title']}. "
                    f"Artist: {metadata['artist']}. "
                    f"Genre: {metadata['genre']}. "
                    f"Audio profile: Tempo is {features['tempo_bpm']:.1f} BPM, "
                    f"energy/loudness level is {features['energy_rmse']:.4f}, "
                    f"brightness/timbre is {features['spectral_centroid']:.1f}."
                )
                
                # Generate embedding
                logger.debug("Generating embedding...")
                embedding_response = client.models.embed_content(
                    model=EMBEDDING_MODEL_ID,
                    contents=description,
                    config={"output_dimensionality": 768}
                )
                embedding = embedding_response.embeddings[0].values
                
                # Use filename as a simple ID
                doc_id = file.replace(' ', '_').replace('.', '_')
                
                # Save to Firestore
                doc_data = {
                    "id": doc_id,
                    "filepath": filepath,
                    "title": metadata['title'],
                    "artist": metadata['artist'],
                    "album": metadata['album'],
                    "genre": metadata['genre'],
                    "audio_features": features,
                    "description_for_search": description,
                    "embedding": Vector(embedding)
                }
                
                collection.document(doc_id).set(doc_data)
                logger.info(f"Successfully ingested {doc_id} to Firestore.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_music.py <path_to_music_directory>")
        sys.exit(1)
        
    target_dir = sys.argv[1]
    if not os.path.isdir(target_dir):
        print(f"Error: Directory '{target_dir}' does not exist.")
        sys.exit(1)
        
    process_directory(target_dir)
