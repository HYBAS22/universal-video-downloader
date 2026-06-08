"""services/trimmer.py — обрезка видео с помощью ffmpeg с точностью до миллисекунд."""

import os
import logging
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("bot")


async def trim_video(
    input_path: str,
    start_time: float,
    end_time: float,
    output_path: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Обрезает видеофайл с помощью ffmpeg с точностью до миллисекунд.
    
    Args:
        input_path: путь к исходному видеофайлу
        start_time: время начала в секундах (float, например 15.450)
        end_time: время окончания в секундах (float, например 20.100)
        output_path: путь для сохранения (если None, создаётся временный файл)
    
    Returns:
        (output_path, error_message) — если успешно, error_message = None
    """
    if not os.path.exists(input_path):
        return None, "Input file not found"
    
    # Валидация времени
    if start_time < 0:
        return None, "Start time cannot be negative"
    if end_time <= start_time:
        return None, "End time must be greater than start time"
    
    duration = end_time - start_time
    if duration < 0.05:  # Уменьшили порог до 50 миллисекунд
        return None, "Trim duration is too short"
    
    if output_path is None:
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"trimmed_{os.urandom(8).hex()}.mp4")
    
    try:
        # Для покадровой точности (миллисекунды) НЕЛЬЗЯ использовать -c copy.
        # Необходимо перекодировать видео. Используем libx264 с пресетом ultrafast для скорости.
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", f"{start_time:.3f}",  # Форматируем до 3 знаков после запятой
            "-to", f"{end_time:.3f}",
            "-i", input_path,
            "-c:v", "libx264",          # Перекодирование видео для точной обрезки
            "-preset", "ultrafast",     # Максимально быстрый рендеринг
            "-crf", "23",               # Сбалансированное качество
            "-c:a", "aac",              # Перекодирование аудио
            "-loglevel", "error",
            output_path,
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            if os.path.exists(output_path):
                os.remove(output_path)
            return None, f"FFmpeg error: {error_msg}"
        
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return None, "Output file is empty"
        
        return output_path, None
    
    except subprocess.TimeoutExpired:
        if os.path.exists(output_path):
            os.remove(output_path)
        return None, "Trim operation timed out"
    except Exception as e:
        log.exception(f"[trimmer] {e}")
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass
        return None, str(e)