import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
import yt_dlp
import requests

app = FastAPI(
    title="YT Music API",
    description="Backend API to feed audio streams to Vibecodeapp with targeted IP bypasses."
)

# 1. BASE OPTIONS: Used for Search and Playlists (Standard Web Scraping)
BASE_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0', # Force IPv4
}

# 2. STREAM OPTIONS: Used ONLY for extracting the final audio file
STREAM_OPTS = {
    **BASE_OPTS,
    # Spoofing the Android app bypasses the strict 403 Forbidden stream blocks
    'extractor_args': {'youtube': {'player_client': ['android']}}
}


@app.get("/")
def root():
    return {"message": "YT Music API is live and properly routing options."}


### 1. SEARCH ENDPOINT ###
@app.get("/search")
def search_yt_music(
    query: str = Query(..., description="Song name or artist"),
    limit: int = Query(10, ge=1, le=20)
):
    opts = {
        **BASE_OPTS,
        'extract_flat': True, 
    }
    
    # Natively use ytsearch syntax
    search_url = f"ytsearch{limit}:{query}"
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    results = []
    
    # If YouTube blocked the search entirely or it failed, return empty array gracefully
    if "entries" not in info:
        return {"query": query, "results": []}
        
    for entry in info["entries"]:
        if not entry:
            continue
            
        results.append({
            "id": entry.get("id"),
            "title": entry.get("title"),
            # ytsearch sometimes uses 'channel' instead of 'uploader'
            "artist": entry.get("channel") or entry.get("uploader", "Unknown Artist"),
            "duration": entry.get("duration"),
            "thumbnail": entry.get("thumbnails")[-1]["url"] if entry.get("thumbnails") else None,
        })
        
    return {"query": query, "results": results}


### 2. STREAM METADATA ENDPOINT ###
@app.get("/stream/{video_id}")
def get_audio_stream_data(video_id: str):
    opts = {
        **STREAM_OPTS, # Use Android spoofing here!
        'format': 'bestaudio/best', 
        'noplaylist': True
    }
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    formats = info.get("formats", [])
    audio_url = None
    for f in formats:
        if f.get("format_id") == info.get("format_id"):
            audio_url = f.get("url")
            break
            
    if not audio_url and formats:
        audio_url = formats[-1].get("url")
    
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "artist": info.get("uploader"),
        "duration": info.get("duration"),
        "direct_url": audio_url,
        "thumbnail": info.get("thumbnail"), 
    }


### 3. PROXY AUDIO STREAM ENDPOINT ###
@app.get("/proxy/{video_id}")
def proxy_audio_stream(video_id: str):
    opts = {
        **STREAM_OPTS, # Use Android spoofing here!
        'format': 'bestaudio/best',
        'noplaylist': True
    }
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    stream_url = info.get("url")
    if not stream_url:
        formats = info.get("formats", [])
        stream_url = formats[-1].get("url") if formats else None

    if not stream_url:
        raise HTTPException(status_code=400, detail="Could not extract stream URL")

    def stream_generator():
        with requests.get(stream_url, stream=True) as r:
            for chunk in r.iter_content(chunk_size=1024 * 1024): 
                if chunk:
                    yield chunk

    return StreamingResponse(stream_generator(), media_type="audio/mp4")


### 4. PLAYLIST ENDPOINT ###
@app.get("/playlist")
def get_playlist(url: str = Query(..., description="YouTube Music Playlist URL")):
    opts = {
        **BASE_OPTS, # Standard web scraping for playlists
        'extract_flat': True
    }
    
    if "youtube.com" in url and "music.youtube.com" not in url:
        url = url.replace("youtube.com", "music.youtube.com")
        
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if "entries" not in info:
        raise HTTPException(status_code=400, detail="Invalid playlist.")

    tracks = []
    for entry in info.get("entries", []):
        tracks.append({
            "id": entry.get("id"),
            "title": entry.get("title"),
            "artist": entry.get("channel") or entry.get("uploader", "Unknown Artist"),
            "duration": entry.get("duration"),
            "thumbnail": entry.get("thumbnails")[-1]["url"] if entry.get("thumbnails") else None
        })
        
    return {
        "playlist_id": info.get("id"),
        "playlist_name": info.get("title"),
        "track_count": len(tracks),
        "tracks": tracks
    }
