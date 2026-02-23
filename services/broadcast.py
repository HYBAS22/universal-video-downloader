"""services/broadcast.py — фоновая отправка рассылок."""

import asyncio
import logging
import database as db
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramForbiddenError
from config import ADMIN_IDS

log = logging.getLogger("bot")


async def send_broadcast(bot: Bot, bc: dict):
    bc_id = bc["id"]
    log.info(f"[broadcast] начало #{bc_id} lang={bc['target_lang']}")
    db.update_broadcast(bc_id, 0, 0, status="sending")

    users = db.all_user_ids(bc["target_lang"])

    kb = None
    if bc.get("btn_text") and bc.get("btn_url"):
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=bc["btn_text"], url=bc["btn_url"])
        ]])

    sent = failed = 0
    for uid in users:
        try:
            await bot.send_message(uid, bc["text"], parse_mode="HTML",
                                   reply_markup=kb, disable_web_page_preview=False)
            sent += 1
        except TelegramForbiddenError:
            db.mark_blocked(uid)
            failed += 1
        except Exception as e:
            log.debug(f"[broadcast] user={uid}: {e}")
            failed += 1
        await asyncio.sleep(0.05)   # 20 msg/sec — в пределах лимитов Telegram

    db.update_broadcast(bc_id, sent, failed, status="done")
    log.info(f"[broadcast] #{bc_id} завершена: {sent} доставлено, {failed} ошибок")

    # Уведомляем всех админов
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"✅ <b>Рассылка #{bc_id} завершена</b>\n\n"
                f"📤 Доставлено: <b>{sent}</b>\n❌ Ошибок: <b>{failed}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass


async def broadcast_scheduler(bot: Bot):
    """Фоновая задача: каждую минуту проверяет и запускает рассылки."""
    while True:
        await asyncio.sleep(60)
        try:
            for bc in db.get_pending_broadcasts():
                asyncio.create_task(send_broadcast(bot, dict(bc)))
        except Exception as e:
            log.exception(f"[broadcast_scheduler] {e}")
