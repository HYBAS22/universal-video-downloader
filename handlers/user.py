"""handlers/user.py — все пользовательские обработчики с поддержкой миллисекунд."""

import os
import logging
import database as db
import services.queue as queue_svc
import services.ads as ads_svc
import services.subscription as sub_svc
import services.trimmer as trimmer_svc

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

from downloader.router import detect, extract_url, download, PLATFORM_NAMES, QUALITY_LABELS
from i18n import t
from config import MAX_FILE_MB, ADMIN_IDS

log = logging.getLogger("bot")
router = Router()


class States(StatesGroup):
    waiting_for_url   = State()
    selecting_quality = State()
    trim_ask_start    = State()
    trim_ask_end      = State()


# ─── Клавиатуры ──────────────────────────────────────────────────────────────

def main_kb(uid: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t(uid, "btn_download"), callback_data="download")],
        [
            InlineKeyboardButton(text=t(uid, "btn_help"),    callback_data="help"),
            InlineKeyboardButton(text=t(uid, "btn_history"), callback_data="history"),
        ],
        [
            InlineKeyboardButton(text=t(uid, "btn_about"),   callback_data="about"),
            InlineKeyboardButton(text=t(uid, "btn_lang"),    callback_data="toggle_lang"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quality_kb(uid: int, platform: str) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text=t(uid, "btn_hd"), callback_data="quality_hd"),
        InlineKeyboardButton(text=t(uid, "btn_sd"), callback_data="quality_sd"),
    ]]
    if platform == "tiktok":
        rows.append([InlineKeyboardButton(text=t(uid, "btn_wm"), callback_data="quality_watermark")])
    if platform == "youtube":
        rows.append([InlineKeyboardButton(text=t(uid, "btn_audio"), callback_data="quality_audio")])
    rows.append([InlineKeyboardButton(text=t(uid, "btn_trim"), callback_data="trim")])
    rows.append([InlineKeyboardButton(text=t(uid, "btn_cancel"), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


# ─── /start, /help ───────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    u = message.from_user
    db.upsert_user(u.id, u.username, u.first_name)
    log.info(f"[/start] user={u.id} @{u.username}")
    await message.answer(
        t(u.id, "start", name=u.first_name, platforms=t(u.id, "platforms")),
        reply_markup=main_kb(u.id, _is_admin(u.id)),
        parse_mode="HTML",
    )


@router.message(Command("help"))
@router.callback_query(F.data == "help")
async def cmd_help(event: Message | CallbackQuery):
    uid = event.from_user.id
    text = t(uid, "help", platforms=t(uid, "platforms"))
    kb   = main_kb(uid, _is_admin(uid))
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "about")
async def callback_about(callback: CallbackQuery):
    uid = callback.from_user.id
    s = db.stats()
    await callback.message.edit_text(
        "ℹ️ <b>Universal Video Downloader</b>\n\n"
        f"👤 Пользователей: <b>{s['total']}</b>\n"
        f"📥 Загрузок сегодня: <b>{s['today_dl']}</b>\n\n"
        "💻 made by @hybikroot",
        parse_mode="HTML",
        reply_markup=main_kb(uid, _is_admin(uid)),
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_lang")
async def toggle_lang(callback: CallbackQuery):
    uid = callback.from_user.id
    new = "en" if db.get_lang(uid) == "ru" else "ru"
    db.set_lang(uid, new)
    await callback.message.edit_text(
        t(uid, "start", name=callback.from_user.first_name, platforms=t(uid, "platforms")),
        reply_markup=main_kb(uid, _is_admin(uid)),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "check_sub")
async def check_sub(callback: CallbackQuery, bot: Bot):
    uid = callback.from_user.id
    if await sub_svc.check_all(bot, uid):
        await callback.message.edit_text(
            t(uid, "sub_ok"), reply_markup=main_kb(uid, _is_admin(uid))
        )
    else:
        await callback.answer(t(uid, "sub_no"), show_alert=True)
    await callback.answer()


# ─── История ─────────────────────────────────────────────────────────────────

@router.message(Command("history"))
@router.callback_query(F.data == "history")
async def show_history(event: Message | CallbackQuery):
    uid = event.from_user.id
    rows = db.get_history(uid)
    if not rows:
        text = t(uid, "history_empty")
    else:
        text = t(uid, "history_title")
        for i, row in enumerate(rows, 1):
            ts   = row["ts"][:16].replace("T", " ")
            pname = PLATFORM_NAMES.get(row["platform"], row["platform"])
            url_short = row["url"][:45] + "..." if len(row["url"]) > 45 else row["url"]
            text += (f"{i}. {pname} · {row['quality']} · {row['size_mb']} МБ\n"
                     f"   <a href='{row['url']}'>{url_short}</a>\n"
                     f"   <i>{ts}</i>\n\n")

    kb = main_kb(uid, _is_admin(uid))
    if isinstance(event, CallbackQuery):
        await event.message.answer(text, parse_mode="HTML", reply_markup=kb,
                                   disable_web_page_preview=True)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb,
                           disable_web_page_preview=True)


# ─── Обработка URL ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "download")
async def cb_download(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    await callback.message.edit_text(
        t(uid, "send_link", platforms=t(uid, "platforms")), parse_mode="HTML"
    )
    await state.set_state(States.waiting_for_url)
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = callback.from_user.id
    await callback.message.edit_text(
        t(uid, "cancel"), reply_markup=main_kb(uid, _is_admin(uid)), parse_mode="HTML"
    )
    await callback.answer()


async def _handle_url(message: Message, state: FSMContext, bot: Bot):
    u = message.from_user
    db.upsert_user(u.id, u.username, u.first_name)

    user = db.get_user(u.id)
    if user and user["is_banned"]:
        await message.answer(t(u.id, "banned"))
        return

    if not await sub_svc.require(bot, message):
        await state.clear()
        return

    url = extract_url(message.text or "")
    if not url:
        await message.answer(t(u.id, "bad_link"))
        return

    platform = detect(url)

    await state.update_data(url=url, platform=platform)
    await message.answer(
        t(u.id, "link_ok", platform=PLATFORM_NAMES[platform]),
        reply_markup=quality_kb(u.id, platform),
        parse_mode="HTML",
    )
    await state.set_state(States.selecting_quality)


@router.message(States.waiting_for_url)
async def process_url_fsm(message: Message, state: FSMContext, bot: Bot):
    await _handle_url(message, state, bot)


@router.message(F.text.regexp(r'https?://'))
async def handle_direct_url(message: Message, state: FSMContext, bot: Bot):
    await _handle_url(message, state, bot)


# ─── Выбор качества → очередь → скачивание ───────────────────────────────────

QUALITY_MAP = {
    "quality_hd": "hd", "quality_sd": "sd",
    "quality_audio": "audio", "quality_watermark": "watermark",
}

def parse_time_to_seconds(text: str) -> float | None:
    """
    Парсит строку в секунды (float). 
    Поддерживает форматы: '15', '15.450', '01:23', '01:23.450'
    """
    text = text.strip().replace(",", ".") # Заменяем запятую на точку на случай ввода '15,4'
    try:
        # Случай 1: Просто число (секунды.миллисекунды) -> "15" или "15.45"
        if ":" not in text:
            return float(text)
        
        # Случай 2: Формат MM:SS или MM:SS.mmm
        parts = text.split(":")
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
            
        # Случай 3: Формат HH:MM:SS.mmm (на всякий случай)
        elif len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
            
        return None
    except ValueError:
        return None


@router.callback_query(F.data == "trim")
async def cb_trim(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    data = await state.get_data()
    
    if not data.get("url"):
        await callback.answer("❌", show_alert=True)
        await state.clear()
        return
    
    await callback.message.edit_text(t(uid, "trim_ask_start"), parse_mode="HTML")
    await state.set_state(States.trim_ask_start)
    await callback.answer()


@router.message(States.trim_ask_start)
async def process_trim_start(message: Message, state: FSMContext):
    uid = message.from_user.id
    # Используем правильную функцию парсинга для поддержки миллисекунд
    start_time = parse_time_to_seconds(message.text or "")
    
    if start_time is None or start_time < 0:
        await message.answer(t(uid, "trim_format_err"), parse_mode="HTML")
        return
    
    await state.update_data(trim_start=start_time)
    await message.answer(t(uid, "trim_ask_end"), parse_mode="HTML")
    await state.set_state(States.trim_ask_end)


@router.message(States.trim_ask_end)
async def process_trim_end(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    data = await state.get_data()
    
    # Используем правильную функцию парсинга для поддержки миллисекунд
    end_time = parse_time_to_seconds(message.text or "")
    start_time = data.get("trim_start", 0)
    
    if end_time is None or end_time < 0:
        await message.answer(t(uid, "trim_format_err"), parse_mode="HTML")
        return
    
    if end_time <= start_time:
        await message.answer(t(uid, "trim_logic_err"), parse_mode="HTML")
        return
    
    url = data.get("url")
    platform = data.get("platform", "unknown")
    
    status_msg = await message.answer(t(uid, "trim_loading"), parse_mode="HTML")
    await state.clear()
    
    async def task():
        await _do_trim(bot, uid, url, platform, start_time, end_time, status_msg, message)
    
    ok = await queue_svc.enqueue_and_wait(task, timeout=300)
    if not ok:
        try:
            await status_msg.edit_text(t(uid, "queue_timeout"),
                                      reply_markup=main_kb(uid, _is_admin(uid)))
        except Exception:
            pass


@router.callback_query(F.data.startswith("quality_"))
async def process_quality(callback: CallbackQuery, state: FSMContext, bot: Bot):
    quality  = QUALITY_MAP.get(callback.data, "hd")
    data     = await state.get_data()
    url      = data.get("url")
    platform = data.get("platform", "unknown")
    uid      = callback.from_user.id

    if not url:
        await callback.answer("❌", show_alert=True)
        await state.clear()
        return

    pos = queue_svc.queue_size() + 1
    label = QUALITY_LABELS.get(quality, quality)

    status_msg = await callback.message.edit_text(
        t(uid, "queue_wait", pos=pos) if pos > 1
        else t(uid, "loading", platform=PLATFORM_NAMES.get(platform, platform), quality=label),
        parse_mode="HTML",
    )
    await callback.answer()
    await state.clear()

    async def task():
        await _do_download(bot, uid, url, platform, quality, label, status_msg, callback)

    ok = await queue_svc.enqueue_and_wait(task, timeout=300)
    if not ok:
        try:
            await status_msg.edit_text(t(uid, "queue_timeout"),
                                       reply_markup=main_kb(uid, _is_admin(uid)))
        except Exception:
            pass


async def _do_trim(bot: Bot, uid: int, url: str, platform: str,
                   start_time: float, end_time: float, status_msg, message: Message):
    """Обрезает скачанное видео."""
    filepath = None
    trimmed_path = None
    
    try:
        # Кэш
        cached = db.cache_get(url)
        if not cached:
            # Нужно сначала скачать
            filepath, error = await download(url, platform, "hd")
            if error or not filepath:
                log.warning(f"[trim] user={uid} download FAIL: {error}")
                try:
                    await status_msg.edit_text(
                        t(uid, "dl_fail", reason=error or "?"),
                        reply_markup=main_kb(uid, _is_admin(uid)), parse_mode="HTML"
                    )
                except Exception:
                    pass
                return
        else:
            file_id, is_audio = cached
            # Кэшированный file_id — нужно скачать с помощью telegram
            # Но это сложно, поэтому скачиваем заново с сайта
            filepath, error = await download(url, platform, "hd")
            if error or not filepath:
                try:
                    await status_msg.edit_text(
                        t(uid, "dl_fail", reason=error or "?"),
                        reply_markup=main_kb(uid, _is_admin(uid)), parse_mode="HTML"
                    )
                except Exception:
                    pass
                return
        
        # Обрезаем видео
        trimmed_path, trim_error = await trimmer_svc.trim_video(
            filepath, start_time, end_time
        )
        
        if trim_error or not trimmed_path:
            log.warning(f"[trim] user={uid} FAIL: {trim_error}")
            try:
                await status_msg.edit_text(
                    t(uid, "trim_fail", reason=trim_error or "?"),
                    reply_markup=main_kb(uid, _is_admin(uid)), parse_mode="HTML"
                )
            except Exception:
                pass
            return
        
        size_mb = os.path.getsize(trimmed_path) / 1024 / 1024
        
        if size_mb > MAX_FILE_MB:
            await status_msg.edit_text(
                t(uid, "too_big", size=f"{size_mb:.1f}"),
                reply_markup=main_kb(uid, _is_admin(uid)), parse_mode="HTML"
            )
            return
        
        await status_msg.edit_text(t(uid, "sending"), parse_mode="HTML")
        caption = t(uid, "trim_done", quality="Trimmed", size=f"{size_mb:.1f}")
        
        file_input = FSInputFile(trimmed_path)
        await message.answer_video(file_input, caption=caption)
        
        db.increment_downloads(uid)
        log.info(f"[trim] user={uid} OK {size_mb:.1f}MB")
        
        try:
            await status_msg.delete()
        except TelegramBadRequest:
            pass
        
        await ads_svc.maybe_show(bot, message.chat.id, uid)
    
    except Exception as e:
        log.exception(f"[trim] send error user={uid}: {e}")
        try:
            await status_msg.edit_text(t(uid, "send_fail"),
                                      reply_markup=main_kb(uid, _is_admin(uid)), parse_mode="HTML")
        except Exception:
            pass
    finally:
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
        if trimmed_path and os.path.exists(trimmed_path):
            try:
                os.remove(trimmed_path)
            except Exception:
                pass


async def _do_download(bot: Bot, uid: int, url: str, platform: str,
                       quality: str, label: str, status_msg, callback: CallbackQuery):
    # Кэш
    cached = db.cache_get(url)
    if cached:
        file_id, is_audio = cached
        try:
            caption = t(uid, "cache_hit", platform=PLATFORM_NAMES.get(platform, platform), quality=label)
            if is_audio:
                await callback.message.answer_audio(file_id, caption=caption, parse_mode="HTML")
            else:
                await callback.message.answer_video(file_id, caption=caption, parse_mode="HTML")
            await status_msg.delete()
            db.add_history(uid, platform, url, quality, 0)
            db.increment_downloads(uid)
            await ads_svc.maybe_show(bot, callback.message.chat.id, uid)
            return
        except Exception:
            pass  # file_id протух — качаем заново

    # Обновляем статус
    try:
        await status_msg.edit_text(
            t(uid, "loading", platform=PLATFORM_NAMES.get(platform, platform), quality=label),
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

    filepath, error = await download(url, platform, quality)

    if error or not filepath:
        log.warning(f"[dl] user={uid} FAIL: {error}")
        try:
            await status_msg.edit_text(
                t(uid, "dl_fail", reason=error or "?"),
                reply_markup=main_kb(uid, _is_admin(uid)), parse_mode="HTML"
            )
        except Exception:
            pass
        return

    try:
        size_mb = os.path.getsize(filepath) / 1024 / 1024

        if size_mb > MAX_FILE_MB:
            await status_msg.edit_text(
                t(uid, "too_big", size=f"{size_mb:.1f}"),
                reply_markup=main_kb(uid, _is_admin(uid)), parse_mode="HTML"
            )
            return

        await status_msg.edit_text(t(uid, "sending"), parse_mode="HTML")
        caption = t(uid, "done",
                    platform=PLATFORM_NAMES.get(platform, platform),
                    quality=label, size=f"{size_mb:.1f}")
        is_audio = (quality == "audio")
        file_input = FSInputFile(filepath)

        if is_audio:
            sent = await callback.message.answer_audio(file_input, caption=caption)
        else:
            sent = await callback.message.answer_video(file_input, caption=caption)

        # Кэшируем file_id
        media = getattr(sent, "audio", None) or getattr(sent, "video", None)
        if media:
            db.cache_set(url, media.file_id, is_audio)

        db.add_history(uid, platform, url, quality, size_mb)
        db.increment_downloads(uid)
        log.info(f"[dl] user={uid} OK {size_mb:.1f}MB")

        try:
            await status_msg.delete()
        except TelegramBadRequest:
            pass

        await ads_svc.maybe_show(bot, callback.message.chat.id, uid)

    except Exception as e:
        log.exception(f"[dl] send error user={uid}: {e}")
        try:
            await status_msg.edit_text(t(uid, "send_fail"),
                                       reply_markup=main_kb(uid, _is_admin(uid)), parse_mode="HTML")
        except Exception:
            pass
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)