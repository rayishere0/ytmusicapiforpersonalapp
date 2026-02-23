import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
import yt_dlp
import requests

app = FastAPI(
    title="YT Music Player API",
    description="A backend API specifically designed to feed audio streams and metadata to a custom music media player, with IP-block bypasses."
)

# Standardized options to bypass YouTube's datacenter blocks
BASE_YTDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    # 1. Force IPv4 to bypass strict IPv6 blocking on datacenters (like Railway)
    'source_address': '0.0.0.0', 
    # 2. Spoof the client as an Android app to bypass web-bot detection
    'extractor_args': {'youtube': {'player_client': ['android']}}
}

def extract_metadata(url: str, custom_opts: dict):
    # Merge the base bypass options with the specific endpoint options
    opts = {**BASE_YTDL_OPTS, **custom_opts}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
def root():
    return {"message": "YT Music API is live and bypassing blocks."}

### 1. SEARCH ENDPOINT ###
@app.get("/search")
def search_yt_music(
    query: str = Query(..., description="Song name or artist"),
    limit: int = Query(10, ge=1, le=20, description="Number of tracks to return")
):
    opts = {
        'extract_flat': True, 
        'default_search': 'ytsearch' # Fallback to standard search format
    }
    
    # Prefixing 'ytmsearch' to specifically target YouTube Music
    search_url = f"ytmsearch{limit}:{query}"
    info = extract_metadata(search_url, opts)
    
    results = []
    for entry in info.get("entries", []):
        results.append({
            "id": entry.get("id"),
            "title": entry.get("title"),
            "artist": entry.get("uploader"),
            "duration": entry.get("duration"),
            "thumbnail": entry.get("thumbnails")[-1]["url"] if entry.get("thumbnails") else None,
        })
        
    return {"query": query, "results": results}


### 2. STREAM METADATA ENDPOINT ###
@app.get("/stream/{video_id}")
def get_audio_stream_data(
    video_id: str
):
    opts = {
        'format': 'bestaudio/best', 
        'noplaylist': True
    }
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    info = extract_metadata(video_url, opts)
    
    # Find the best audio format URL
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
        "direct_url": audio_url, # Useful for metadata, but triggers 403s if played locally
        "thumbnail": info.get("thumbnail"), 
    }

### 3. PROXY AUDIO STREAM ENDPOINT (THE FIX FOR 403 ERRORS) ###
@app.get("/proxy/{video_id}")
def proxy_audio_stream(video_id: str):
    """
    Downloads audio from YouTube to the Railway server in chunks, 
    and instantly streams it to the user. Prevents local IP mismatch.
    """
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True
    }
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    info = extract_metadata(video_url, opts)
    
    stream_url = info.get("url")
    if not stream_url:
        formats = info.get("formats", [])
        stream_url = formats[-1].get("url") if formats else None

    if not stream_url:
        raise HTTPException(status_code=400, detail="Could not extract stream URL")

    # Generator to stream the file in 1MB chunks
    def stream_generator():
        with requests.get(stream_url, stream=True) as r:
            for chunk in r.iter_content(chunk_size=1024 * 1024): 
                if chunk:
                    yield chunk

    return StreamingResponse(stream_generator(), media_type="audio/mp4")

@app.get("/health")
def health_check():
    return {"status": "OK"}


### 4. PLAYLIST ENDPOINT ###
@app.get("/playlist")
def get_playlist(
    url: str = Query(..., description="YouTube Music Playlist URL")
):
    opts = {
        'extract_flat': True
    }
    
    if "youtube.com" in url and "music.youtube.com" not in url:
        url = url.replace("youtube.com", "music.youtube.com")
        
    info = extract_metadata(url, opts)
    
    if "entries" not in info:
        raise HTTPException(status_code=400, detail="Invalid playlist.")

    tracks = []
    for entry in info.get("entries", []):
        tracks.append({
            "id": entry.get("id"),
            "title": entry.get("title"),
            "artist": entry.get("uploader"),
            "duration": entry.get("duration"),
            "thumbnail": entry.get("thumbnails")[-1]["url"] if entry.get("thumbnails") else None
        })
        
    return {
        "playlist_id": info.get("id"),
        "playlist_name": info.get("title"),
        "track_count": len(tracks),
        "tracks": tracks
    }
