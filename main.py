import os
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
import yt_dlp

# Metadata for the automatic Documentation
app = FastAPI(
    title="VibeCode Music API",
    description="Backend API for high-performance audio streaming and metadata extraction.",
    version="2.0.0",
    openapi_tags=[
        {"name": "Discovery", "description": "Search and Playlist extraction logic."},
        {"name": "Streaming", "description": "High-level proxying and audio stream extraction."},
    ]
)

# 2026 Anti-Bot Bypass Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
}

BASE_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'nocheckcertificate': True,
}

STREAM_OPTS = {
    **BASE_OPTS,
    'extractor_args': {
        'youtube': {
            'player_client': ['default', '-android_sdkless'],
            'skip_js_check': False 
        }
    },
    'http_headers': HEADERS
}

### 1. SEARCH ENDPOINT ###
@app.get("/search", tags=["Discovery"], summary="Search YouTube Music")
def search_yt_music(
    query: str = Query(..., description="Song name or artist"),
    limit: int = Query(10, ge=1, le=20)
):
    opts = {**BASE_OPTS, 'extract_flat': True}
    search_url = f"ytsearch{limit}:{query}"
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            results = []
            for entry in info.get("entries", []):
                if not entry: continue
                results.append({
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "artist": entry.get("channel") or entry.get("uploader"),
                    "duration": entry.get("duration"),
                    "thumbnail": entry.get("thumbnails")[-1]["url"] if entry.get("thumbnails") else None,
                })
            return {"query": query, "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

### 2. PLAYLIST ENDPOINT ###
@app.get("/playlist", tags=["Discovery"], summary="Extract Playlist Tracks")
def get_playlist(url: str = Query(..., description="YouTube/YT Music Playlist URL")):
    opts = {**BASE_OPTS, 'extract_flat': True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            tracks = [{
                "id": e.get("id"),
                "title": e.get("title"),
                "artist": e.get("channel"),
                "duration": e.get("duration"),
                "thumbnail": e.get("thumbnails")[-1]["url"] if e.get("thumbnails") else None
            } for e in info.get("entries", [])]
            return {"playlist_name": info.get("title"), "tracks": tracks}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

### 3. STREAM METADATA ENDPOINT ###
@app.get("/stream/{video_id}", tags=["Streaming"], summary="Get Raw Stream Info")
def get_stream_data(video_id: str):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(STREAM_OPTS) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {
                "id": info.get("id"),
                "title": info.get("title"),
                "direct_url": info.get("url"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration")
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

### 4. PROXY AUDIO STREAM ENDPOINT ###
@app.get("/proxy/{video_id}", tags=["Streaming"], summary="Proxy Audio (Bypass 403)")
def proxy_audio_stream(video_id: str):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(STREAM_OPTS) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info.get("url") or info.get("formats", [{}])[-1].get("url")
            
            def stream_generator():
                with requests.get(stream_url, stream=True, headers=HEADERS) as r:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk: yield chunk
            return StreamingResponse(stream_generator(), media_type="audio/mp4")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/", include_in_schema=False)
def root():
    return {"status": "Online", "docs": "/docs"}
