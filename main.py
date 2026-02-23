import os
from fastapi import FastAPI, HTTPException, Query
import yt_dlp

app = FastAPI(
    title="YT Music Player API",
    description="A backend API specifically designed to feed audio streams and metadata to a custom music media player."
)

def extract_metadata(url: str, opts: dict):
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
def root():
    return {"message": "YT Music API is live."}

### 1. YOUTUBE MUSIC SEARCH ENDPOINT ###
@app.get("/search")
def search_yt_music(
    query: str = Query(..., description="Song name or artist"),
    limit: int = Query(10, ge=1, le=20, description="Number of tracks to return")
):
    opts = {
        'extract_flat': True, 
        'quiet': True,
        # Default to YouTube Music search to avoid standard YT video clutter
        'default_search': 'ytmsearch' 
    }
    
    # ytmsearch specifically targets music.youtube.com
    search_url = f"ytmsearch{limit}:{query}"
    info = extract_metadata(search_url, opts)
    
    results = []
    for entry in info.get("entries", []):
        results.append({
            "id": entry.get("id"),
            "title": entry.get("title"),
            "artist": entry.get("uploader"), # Uploader is usually the Artist in YT Music
            "duration": entry.get("duration"),
            # Grabbing the last thumbnail usually provides the highest resolution for a GUI
            "thumbnail": entry.get("thumbnails")[-1]["url"] if entry.get("thumbnails") else None,
        })
        
    return {"query": query, "results": results}


### 2. STREAMING & NOW PLAYING METADATA ENDPOINT ###
@app.get("/stream/{video_id}")
def get_audio_stream(
    video_id: str
):
    opts = {
        # bestaudio grabs the highest quality m4a or webm (opus) stream
        'format': 'bestaudio/best', 
        'quiet': True,
        'noplaylist': True
    }
    
    # We use the standard watch URL, but grab only the audio
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    info = extract_metadata(video_url, opts)
    
    # Find the best audio format URL
    formats = info.get("formats", [])
    audio_url = None
    for f in formats:
        if f.get("format_id") == info.get("format_id"):
            audio_url = f.get("url")
            break
            
    # Fallback if specific format_id match fails
    if not audio_url and formats:
        audio_url = formats[-1].get("url")
    
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "artist": info.get("uploader"),
        "duration": info.get("duration"),
        "stream_url": audio_url, # Pass this directly to your audio engine (e.g., VLC, Pygame, mpv)
        "thumbnail": info.get("thumbnail"), # High-res cover art for the player UI
        "tags": info.get("tags", [])
    }


### 3. YT MUSIC PLAYLIST ENDPOINT ###
@app.get("/playlist")
def get_playlist(
    url: str = Query(..., description="YouTube Music Playlist URL")
):
    opts = {
        'extract_flat': True,
        'quiet': True
    }
    
    # Ensure it's treated as a YT Music URL if the user pastes a standard YT playlist
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