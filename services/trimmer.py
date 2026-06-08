"""services/trimmer.py — обрезка видео с помощью ffmpeg."""

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
    Обрезает видеофайл с помощью ffmpeg.
    
    Args:
        input_path: путь к исходному видеофайлу
        start_time: время начала в секундах
        end_time: время окончания в секундах
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
    if duration < 0.1:
        return None, "Trim duration is too short"
    
    # Если output_path не указан, создаём временный файл
    if output_path is None:
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"trimmed_{os.urandom(8).hex()}.mp4")
    
    try:
        # Используем ffmpeg для обрезки видео
        # -ss: начальная позиция
        # -to: конечная позиция
        # -c:v copy -c:a copy: копируем видео/аудио без перекодирования (быстро)
        cmd = [
            "ffmpeg",
            "-y",  # перезаписать без подтверждения
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", input_path,
            "-c:v", "copy",
            "-c:a", "copy",
            "-loglevel", "error",
            output_path,
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 минуты максимум
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
