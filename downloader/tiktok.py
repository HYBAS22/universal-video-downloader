import asyncio
import logging
import os
from config import DOWNLOAD_DIR
from downloader.ytdlp import download as ytdlp_download

log = logging.getLogger("bot")


async def download(url: str, quality: str) -> tuple[str | None, str | None]:
    """TikTok скачивание через yt-dlp (более надежно чем API)"""
    log.info(f"[TikTok] downloading via yt-dlp quality={quality}")
    try:
        result = await ytdlp_download(url, quality)
        if result[0]:
            log.info("[TikTok] ✓")
            return result
    except Exception as e:
        log.error(f"[TikTok] yt-dlp failed: {e}")
    
    return None, "TikTok скачивание не удалось"
