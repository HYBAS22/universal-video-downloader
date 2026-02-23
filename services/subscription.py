"""services/subscription.py — проверка подписки на каналы."""

import logging
import database as db
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from i18n import t, t_sub_req                          # ← добавлен t_sub_req

log = logging.getLogger("bot")


async def check_all(bot: Bot, user_id: int) -> bool:
    """True если пользователь подписан на все активные каналы."""
    if not int(db.get_setting("sub_required", "1")):
        return True
    channels = db.get_channels(enabled_only=True)
    if not channels:
        return True
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ("left", "kicked", "restricted"):
                return False
        except Exception as e:
            log.warning(f"[sub] channel={ch['channel_id']} err: {e}")
    return True


async def require(bot: Bot, message: Message) -> bool:
    """Отправляет требование подписки если нужно. Возвращает False если заблокировано."""
    uid = message.from_user.id
    if await check_all(bot, uid):
        return True

    channels = db.get_channels(enabled_only=True)
    channels_text = "\n".join(
        f"• <a href='{ch['url']}'>{ch['title']}</a>" for ch in channels
    )

    buttons = [
        [InlineKeyboardButton(text=ch["title"], url=ch["url"])]
        for ch in channels
    ]
    buttons.append([
        InlineKeyboardButton(
            text=t(uid, "btn_subscribed"),
            callback_data="check_sub",
        )
    ])

    # ─── ИСПРАВЛЕНО: вместо t(uid, "sub_req", ...) ───
    await message.answer(
        t_sub_req(uid, channels_text, len(channels)),   # ← вот эта строка
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    log.info(f"[sub] user={uid} заблокирован — не подписан")
    return False