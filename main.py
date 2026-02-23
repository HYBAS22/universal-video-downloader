import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
import services.queue as queue_svc
from services.broadcast import broadcast_scheduler
from handlers.user import router as user_router
from handlers.admin_panel import router as admin_router
from config import BOT_TOKEN, DOWNLOAD_DIR, LOG_DIR


def setup_logging():
    Path(LOG_DIR).mkdir(exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("bot")
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    fh = RotatingFileHandler(f"{LOG_DIR}/bot.log",
                             maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)


async def main():
    setup_logging()
    log = logging.getLogger("bot")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    db.init()

    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров (порядок важен — admin раньше user чтобы admin:* callbacks не перехватывались)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Запуск фоновых сервисов
    queue_svc.start()
    asyncio.create_task(broadcast_scheduler(bot))

    s = db.get_all_settings()
    log.info("=" * 55)
    log.info("🤖 Universal Video Downloader запущен")
    log.info(f"   Воркеров: {s.get('queue_workers', 5)}")
    log.info(f"   Реклама каждые: {s.get('ad_every_n', 3)} загрузок")
    log.info(f"   Кэш TTL: {s.get('cache_ttl_hours', 24)}ч")
    log.info(f"   Подписка: {'вкл' if int(s.get('sub_required', 1)) else 'выкл'}")
    log.info("=" * 55)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
