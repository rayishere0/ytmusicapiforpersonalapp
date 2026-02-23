import os
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
import yt_dlp

app = FastAPI()

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

# The "Magic" arguments for 2026
STREAM_OPTS = {
    **BASE_OPTS,
    'extractor_args': {
        'youtube': {
            # 'default' client with the newer 'android' bypass
            'player_client': ['default', '-android_sdkless'],
            # Tells yt-dlp to use a JS runtime if found (Deno)
            'skip_js_check': False 
        }
    },
    'http_headers': HEADERS
}

def extract_with_retry(url, opts):
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        # If still blocked, we raise a clear error
        if "confirm you're not a bot" in str(e):
            raise HTTPException(status_code=403, detail="YouTube Bot Detection Triggered. Render IP might be flagged.")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/proxy/{video_id}")
def proxy_audio_stream(video_id: str):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    info = extract_with_retry(video_url, STREAM_OPTS)
    
    stream_url = info.get("url") or info.get("formats", [{}])[-1].get("url")
    
    if not stream_url:
        raise HTTPException(status_code=400, detail="Could not find audio stream.")

    def stream_generator():
        # Passing our browser headers to the actual stream request
        with requests.get(stream_url, stream=True, headers=HEADERS) as r:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    yield chunk

    return StreamingResponse(stream_generator(), media_type="audio/mp4")

# Search and Playlist remain the same but use BASE_OPTS
