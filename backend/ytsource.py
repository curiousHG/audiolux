"""YouTube search + audio download (yt-dlp + ffmpeg), cached by video id.

Search uses a flat extract (no per-video network round-trips) so it returns in
~1 s. Download grabs best audio and transcodes to a browser-friendly mp3 that the
frontend <audio> element can stream (with Range/seek). Everything is cached under
`cache/` so replaying a track is instant.
"""
import os

import yt_dlp

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(_HERE, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def audio_path(vid: str) -> str:
    return os.path.join(CACHE_DIR, f"{vid}.mp3")


def is_cached(vid: str) -> bool:
    p = audio_path(vid)
    return os.path.exists(p) and os.path.getsize(p) > 0


def search(query: str, n: int = 12) -> list[dict]:
    """Flat YouTube search — fast, metadata only (no download)."""
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(f"ytsearch{n}:{query}", download=False)
    out = []
    for e in info.get("entries", []) or []:
        if not e or not e.get("id"):
            continue
        out.append({
            "id": e["id"],
            "title": e.get("title") or "(untitled)",
            "uploader": e.get("uploader") or e.get("channel") or "",
            "duration": int(e.get("duration") or 0),
        })
    return out


def download(vid: str, progress_cb=None) -> str:
    """Download best audio for `vid`, transcode to cache/<vid>.mp3, return the path.
    Idempotent — returns immediately if already cached. `progress_cb(fraction)` is
    called with 0..1 during the download."""
    dst = audio_path(vid)
    if is_cached(vid):
        if progress_cb:
            progress_cb(1.0)
        return dst

    def _hook(d):
        if not progress_cb:
            return
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if total:
                progress_cb(min(0.95, done / total))
        elif d["status"] == "finished":
            progress_cb(0.97)            # transcode still to come

    opts = {
        "quiet": True, "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": os.path.join(CACHE_DIR, "%(id)s.%(ext)s"),
        "progress_hooks": [_hook],
        "postprocessors": [{"key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3", "preferredquality": "192"}],
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as y:
        y.download([f"https://www.youtube.com/watch?v={vid}"])
    if progress_cb:
        progress_cb(1.0)
    return dst


def meta(vid: str) -> dict:
    """Full metadata for one video (title/duration) — used after a search pick."""
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    return {"id": vid, "title": info.get("title") or vid,
            "uploader": info.get("uploader") or "", "duration": int(info.get("duration") or 0)}
