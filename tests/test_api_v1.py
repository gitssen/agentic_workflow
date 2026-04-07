import pytest
import httpx
import json
import base64
import os
from api_proto import api_pb2

BASE_URL = "http://localhost:8000"

@pytest.mark.asyncio
async def test_songs_json():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{BASE_URL}/songs?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "id" in data[0]
            assert "title" in data[0]

@pytest.mark.asyncio
async def test_personas_json():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{BASE_URL}/personas")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert "music_curator" in data

@pytest.mark.asyncio
async def test_negotiation_protobuf():
    # This will fail initially because we haven't implemented it yet
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Requesting protobuf via Accept header
        response = await client.get(
            f"{BASE_URL}/songs?limit=5", 
            headers={"Accept": "application/x-protobuf"}
        )
        # If the migration works, this should return binary protobuf
        # and Content-Type should be application/x-protobuf
        if response.status_code == 200 and response.headers.get("Content-Type") == "application/x-protobuf":
            songs_res = api_pb2.ListSongsResponse()
            songs_res.ParseFromString(response.content)
            assert len(songs_res.songs) > 0
            print("Successfully received and parsed Protobuf!")
        else:
            pytest.fail(f"Negotiation failed or not implemented. CT: {response.headers.get('Content-Type')}")

@pytest.mark.asyncio
async def test_curate_protobuf_post():
    async with httpx.AsyncClient(timeout=30.0) as client:
        req = api_pb2.CuratePlaylistRequest(prompt="Some happy music")
        binary_req = req.SerializeToString()
        
        response = await client.post(
            f"{BASE_URL}/curate_playlist",
            content=binary_req,
            headers={
                "Content-Type": "application/x-protobuf",
                "Accept": "application/x-protobuf"
            }
        )
        
        if response.status_code == 200:
            res = api_pb2.CuratePlaylistResponse()
            res.ParseFromString(response.content)
            assert res.status == "success"
            assert len(res.playlist) > 0
        else:
            pytest.fail(f"Protobuf POST failed: {response.status_code}")
