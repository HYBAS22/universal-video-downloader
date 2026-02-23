"""downloader/router.py — роутер: выбирает метод загрузки по платформе."""

import logging
import re
from downloader import tiktok, ytdlp

log = logging.getLogger("bot")

PLATFORM_PATTERNS = {
    "tiktok":    r'https?://(?:www\.|vm\.|vt\.|m\.)?tiktok\.com/\S+',
    "youtube":   r'https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)\S+',
    "instagram": r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/\S+',
    "twitter":   r'https?://(?:www\.)?(?:twitter|x)\.com/\S+/status/\d+',
    "vk":        r'https?://(?:www\.)?vk\.com/(?:video|clip)\S+',
}

PLATFORM_NAMES = {
    "tiktok": "TikTok", "youtube": "YouTube",
    "instagram": "Instagram", "twitter": "Twitter / X", "vk": "VK",
}

QUALITY_LABELS = {
    "hd": "HD 1080p", "sd": "SD 480p",
    "audio": "Audio", "watermark": "Watermark",
}


def detect(url: str) -> str | None:
    for p, pat in PLATFORM_PATTERNS.items():
        if re.search(pat, url, re.IGNORECASE):
            return p
    return None


def extract_url(text: str) -> str | None:
    m = re.search(r'https?://\S+', text)
    return m.group(0) if m else None


async def download(url: str, platform: str, quality: str) -> tuple[str | None, str | None]:
    """
    TikTok → API сначала, потом yt-dlp fallback.
    Всё остальное → yt-dlp напрямую.
    """
    if platform == "tiktok":
        fp, err = await tiktok.download(url, quality)
        if fp:
            return fp, None
        log.info(f"[router] TikTok API fail ({err}), fallback yt-dlp")
        q = quality if quality != "watermark" else "best"
        return await ytdlp.download(url, q)

    return await ytdlp.download(url, quality)
