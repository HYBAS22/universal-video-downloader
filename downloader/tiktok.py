"""downloader/tiktok.py — TikTok через API (TikWM → TikMate → SSSTik)."""

import re
import logging
import aiohttp
from pathlib import Path
from config import DOWNLOAD_DIR

log = logging.getLogger("bot")
_H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


async def _tikwm(url: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://www.tikwm.com/api/?url={url}",
                             headers=_H, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("code") == 0:
                        return data
    except Exception as e:
        log.debug(f"[TikWM] {e}")
    return None


async def _tikmate(url: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://tikmate.app/api/downloader",
                json={"url": url},
                headers={**_H, "Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                if r.status == 200:
                    return await r.json()
    except Exception as e:
        log.debug(f"[TikMate] {e}")
    return None


async def _ssstik(url: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://ssstik.io/abc?url=dl",
                data={"id": url, "locale": "en", "tt": "temp"},
                headers={**_H, "Content-Type": "application/x-www-form-urlencoded"},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                if r.status == 200:
                    html = await r.text()
                    m = re.search(r'href="([^"]+)"[^>]*>download', html, re.IGNORECASE)
                    if m:
                        return {"video_url": m.group(1)}
    except Exception as e:
        log.debug(f"[SSSTik] {e}")
    return None


async def _fetch(video_url: str, dest: str) -> bool:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                video_url,
                headers={**_H, "Referer": "https://www.tiktok.com/"},
                timeout=aiohttp.ClientTimeout(total=60)
            ) as r:
                if r.status == 200:
                    content = await r.read()
                    if len(content) < 1000:
                        return False
                    Path(dest).write_bytes(content)
                    return True
    except Exception as e:
        log.debug(f"[fetch] {e}")
    return False


async def download(url: str, quality: str) -> tuple[str | None, str | None]:
    dest = f"{DOWNLOAD_DIR}/tt_{abs(hash(url))}.mp4"

    log.info(f"[TikTok] TikWM quality={quality}")
    data = await _tikwm(url)
    if data:
        vd = data.get("data", {})
        link = (vd.get("hdplay") if quality == "hd"
                else vd.get("wmplay") if quality == "watermark"
                else vd.get("play")) or vd.get("play")
        if link and await _fetch(link, dest):
            log.info("[TikTok] TikWM ✓")
            return dest, None

    log.info("[TikTok] TikMate")
    data = await _tikmate(url)
    if data:
        token = data.get("token")
        if token and await _fetch(f"https://tikmate.app{token}", dest):
            log.info("[TikTok] TikMate ✓")
            return dest, None

    log.info("[TikTok] SSSTik")
    data = await _ssstik(url)
    if data:
        link = data.get("video_url")
        if link and await _fetch(link, dest):
            log.info("[TikTok] SSSTik ✓")
            return dest, None

    log.warning("[TikTok] все API недоступны")
    return None, "Все TikTok API недоступны"
