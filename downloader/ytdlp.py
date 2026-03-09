import asyncio
import logging
import os
from config import DOWNLOAD_DIR

log = logging.getLogger("bot")

FORMATS = {
    "hd":        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "sd":        "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]",
    "audio":     "bestaudio[ext=m4a]/bestaudio",
    "watermark": "best",
    "best":      "best",
}


async def download(url: str, quality: str = "hd") -> tuple[str | None, str | None]:
    fmt = FORMATS.get(quality, FORMATS["hd"])
    out = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    base_cmd = [
        "yt-dlp", "-f", fmt,
        "--no-playlist", "--no-warnings",
        "--socket-timeout", "30", "--retries", "3",
        "-o", out, "--print", "after_move:filepath",
    ]

    if quality != "audio":
        base_cmd += ["--merge-output-format", "mp4"]

    cmd = base_cmd + [url]
    log.info(f"[yt-dlp] url={url[:60]} quality={quality}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            err = stderr.decode(errors="replace").strip()
            log.error(f"[yt-dlp] code={proc.returncode}: {err[:300]}")
            if "Video unavailable" in err or "removed" in err.lower():
                return None, "Видео удалено или недоступно."
            if "Private video" in err:
                return None, "Приватное видео."
            if "age" in err.lower():
                return None, "Возрастное ограничение."
            if "copyright" in err.lower():
                return None, "Заблокировано из-за авторских прав."
            return None, "yt-dlp не смог скачать."

        filepath = stdout.decode(errors="replace").strip().splitlines()[-1].strip()
        if not filepath or not os.path.exists(filepath):
            return None, "Файл не найден после загрузки."

        log.info(f"[yt-dlp] ✓ {filepath}")
        return filepath, None

    except asyncio.TimeoutError:
        log.error("[yt-dlp] timeout")
        return None, "Превышено время ожидания."
    except FileNotFoundError:
        log.critical("[yt-dlp] не установлен!")
        return None, "yt-dlp не установлен на сервере."
    except Exception as e:
        log.exception(f"[yt-dlp] {e}")
        return None, str(e)
