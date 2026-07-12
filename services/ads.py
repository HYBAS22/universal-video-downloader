"""services/ads.py — показ партнёрской рекламы."""

import logging
import database as db
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger("bot")

_ad_index = 0  # глобальный счётчик ротации


async def maybe_show(bot: Bot, chat_id: int, user_id: int):
    global _ad_index

    every_n = int(db.get_setting("ad_every_n", "3"))
    if every_n == 0:
        log.debug(f"[ad] skip: ad_every_n=0 (выключено)")
        return

    # FIX: берём total_downloads из таблицы users
    # Раньше: db.get_daily_count(user_id) → всегда 0
    # Теперь: db.get_user() → total_downloads (обновляется increment_downloads)
    user = db.get_user(user_id)
    if not user:
        log.debug(f"[ad] skip: user={user_id} не найден")
        return

    total = user["total_downloads"]
    log.info(
        f"[ad] check user={user_id} total_dl={total} "
        f"every_n={every_n} mod={total % every_n}"
    )

    if total == 0 or total % every_n != 0:
        return

    ads = db.get_ads(enabled_only=True)
    if not ads:
        log.info(f"[ad] skip: нет активных объявлений")
        return

    ad = ads[_ad_index % len(ads)]
    _ad_index += 1

    kb = None
    if ad["btn_text"] and ad["btn_url"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=ad["btn_text"], url=ad["btn_url"])
        ]])

    try:
        await bot.send_message(
            chat_id, ad["text"],
            parse_mode="HTML",
            reply_markup=kb,
            disable_web_page_preview=False,
        )
        db.increment_ad_shows(ad["id"])
        log.info(f"[ad] ✅ id={ad['id']} '{ad['title']}' → user={user_id}")
    except Exception as e:
        log.warning(f"[ad] ошибка отправки: {e}")