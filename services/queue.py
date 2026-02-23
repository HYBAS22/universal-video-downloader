"""services/queue.py — очередь загрузок."""

import asyncio
import logging
import database as db

log = logging.getLogger("bot")

_queue: asyncio.Queue = asyncio.Queue()
_worker_tasks: list = []


async def _worker():
    while True:
        task_fn = await _queue.get()
        try:
            await task_fn()
        except Exception as e:
            log.exception(f"[worker] {e}")
        finally:
            _queue.task_done()


def start(n: int | None = None):
    count = n or int(db.get_setting("queue_workers", "5"))
    for _ in range(count):
        _worker_tasks.append(asyncio.create_task(_worker()))
    log.info(f"[queue] запущено {count} воркеров")


async def enqueue_and_wait(task_fn, timeout: int = 300) -> bool:
    """
    Добавляет задачу в очередь и ждёт её выполнения.
    Возвращает False при timeout.
    """
    done = asyncio.Event()

    async def wrapped():
        await task_fn()
        done.set()

    await _queue.put(wrapped)
    try:
        await asyncio.wait_for(done.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False


def queue_size() -> int:
    return _queue.qsize()
