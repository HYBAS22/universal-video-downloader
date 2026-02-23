"""
handlers/admin_panel.py — полная инлайн-панель администратора.

Навигация через callback_data формата "admin:<раздел>:<действие>:<аргумент>"

Разделы:
  home        — главное меню панели
  stats       — статистика
  channels    — управление каналами подписки
  ads         — рекламные объявления
  broadcasts  — рассылки
  users       — поиск и управление пользователями
  settings    — глобальные настройки
"""

import re
import logging
from datetime import datetime, timezone, timedelta

import database as db
import services.broadcast as bc_svc

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from config import ADMIN_IDS, TZ_OFFSET

log = logging.getLogger("bot")
router = Router()


# ─── FSM для создания объектов из панели ─────────────────────────────────────

class AdminStates(StatesGroup):
    # Каналы
    channel_add_id    = State()
    channel_add_title = State()
    channel_add_url   = State()
    # Реклама
    ad_add_title   = State()
    ad_add_text    = State()
    ad_add_button  = State()
    # Рассылка
    bc_text   = State()
    bc_button = State()
    bc_lang   = State()
    bc_time   = State()
    # Пользователи
    user_search = State()
    # Настройки
    setting_edit = State()


# ─── Фильтр: только для админов ──────────────────────────────────────────────

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


# ─── Вспомогательные клавиатуры ──────────────────────────────────────────────

def _back(section: str = "home") -> list:
    return [[InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:{section}")]]


def home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика",       callback_data="admin:stats")],
        [InlineKeyboardButton(text="📢 Каналы подписки",  callback_data="admin:channels")],
        [InlineKeyboardButton(text="📣 Реклама",          callback_data="admin:ads")],
        [InlineKeyboardButton(text="📬 Рассылки",         callback_data="admin:broadcasts")],
        [InlineKeyboardButton(text="👥 Пользователи",     callback_data="admin:users")],
        [InlineKeyboardButton(text="⚙️ Настройки",        callback_data="admin:settings")],
        [InlineKeyboardButton(text="❌ Закрыть",          callback_data="admin:close")],
    ])


# ─── Открытие панели ─────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    s = db.stats()
    await message.answer(
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"👤 Пользователей: <b>{s['total']}</b> (+{s['new_today']} сегодня)\n"
        f"📥 Загрузок сегодня: <b>{s['today_dl']}</b>  |  Всего: <b>{s['total_dl']}</b>",
        reply_markup=home_kb(), parse_mode="HTML",
    )


@router.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    s = db.stats()
    await callback.message.edit_text(
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"👤 Пользователей: <b>{s['total']}</b> (+{s['new_today']} сегодня)\n"
        f"📥 Загрузок сегодня: <b>{s['today_dl']}</b>  |  Всего: <b>{s['total_dl']}</b>",
        reply_markup=home_kb(), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:close")
async def admin_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
#  📊 СТАТИСТИКА
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    s = db.stats()
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👤 Всего пользователей: <b>{s['total']}</b>\n"
        f"   🇷🇺 RU: <b>{s['ru']}</b>  |  🇬🇧 EN: <b>{s['en']}</b>\n"
        f"   🚫 Забанено: <b>{s['banned']}</b>\n"
        f"   🆕 Новых сегодня: <b>{s['new_today']}</b>\n\n"
        f"📥 Загрузок сегодня: <b>{s['today_dl']}</b>\n"
        f"📦 Загрузок всего: <b>{s['total_dl']}</b>\n\n"
    )
    # Статистика рекламы
    ads = db.get_ads()
    if ads:
        text += "📣 <b>Реклама:</b>\n"
        for ad in ads:
            status = "✅" if ad["enabled"] else "⏸"
            text += f"  {status} #{ad['id']} <i>{ad['title']}</i> — {ad['shows']} показов\n"

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:stats")],
            *_back(),
        ])
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
#  📢 КАНАЛЫ ПОДПИСКИ
# ══════════════════════════════════════════════════════════════════════════════

def _channels_kb() -> InlineKeyboardMarkup:
    channels = db.get_channels()
    rows = []
    for ch in channels:
        status = "✅" if ch["enabled"] else "⏸"
        rows.append([
            InlineKeyboardButton(
                text=f"{status} {ch['title']}",
                callback_data=f"admin:ch_toggle:{ch['id']}"
            ),
            InlineKeyboardButton(text="🗑", callback_data=f"admin:ch_del:{ch['id']}"),
        ])

    # Переключатель обязательности подписки
    sub_on = int(db.get_setting("sub_required", "1"))
    rows.append([InlineKeyboardButton(
        text=f"{'🔒 Подписка: ВКЛ' if sub_on else '🔓 Подписка: ВЫКЛ'} — нажми чтобы переключить",
        callback_data="admin:sub_toggle"
    )])
    rows.append([InlineKeyboardButton(text="➕ Добавить канал", callback_data="admin:ch_add")])
    rows += _back()
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "admin:channels")
async def admin_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    channels = db.get_channels()
    sub_on   = int(db.get_setting("sub_required", "1"))
    text = (
        f"📢 <b>Каналы подписки</b>\n\n"
        f"Обязательная подписка: <b>{'ВКЛ 🔒' if sub_on else 'ВЫКЛ 🔓'}</b>\n"
        f"Каналов: <b>{len(channels)}</b>\n\n"
        + ("\n".join(f"• {'✅' if ch['enabled'] else '⏸'} {ch['title']} (<code>{ch['channel_id']}</code>)"
                     for ch in channels) or "<i>Нет каналов</i>")
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_channels_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:sub_toggle")
async def admin_sub_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    current = int(db.get_setting("sub_required", "1"))
    db.set_setting("sub_required", str(1 - current))
    await admin_channels(callback)


@router.callback_query(F.data.startswith("admin:ch_toggle:"))
async def admin_ch_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    row_id = int(callback.data.split(":")[-1])
    db.toggle_channel(row_id)
    await admin_channels(callback)


@router.callback_query(F.data.startswith("admin:ch_del:"))
async def admin_ch_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    row_id = int(callback.data.split(":")[-1])
    db.delete_channel(row_id)
    await callback.answer("✅ Канал удалён")
    await admin_channels(callback)


# Добавление канала — 3 шага

@router.callback_query(F.data == "admin:ch_add")
async def admin_ch_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "📢 <b>Добавить канал</b>\n\n"
        "Шаг 1/3: Отправь <b>username или ID</b> канала.\n\n"
        "Примеры: <code>@mychannel</code> или <code>-1001234567890</code>\n\n"
        "Бот должен быть <b>администратором</b> этого канала.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=_back("channels")),
    )
    await state.set_state(AdminStates.channel_add_id)
    await callback.answer()


@router.message(AdminStates.channel_add_id)
async def admin_ch_add_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(ch_id=message.text.strip())
    await message.answer(
        "Шаг 2/3: Отправь <b>название</b> канала (как оно будет отображаться пользователям).",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.channel_add_title)


@router.message(AdminStates.channel_add_title)
async def admin_ch_add_title(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(ch_title=message.text.strip())
    await message.answer("Шаг 3/3: Отправь <b>ссылку</b> на канал (https://t.me/...).",
                         parse_mode="HTML")
    await state.set_state(AdminStates.channel_add_url)


@router.message(AdminStates.channel_add_url)
async def admin_ch_add_url(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    db.add_channel(data["ch_id"], data["ch_title"], message.text.strip())
    await state.clear()
    log.info(f"[admin] добавлен канал {data['ch_id']}")
    await message.answer(
        f"✅ Канал <b>{data['ch_title']}</b> добавлен!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ К каналам", callback_data="admin:channels")
        ]])
    )


# ══════════════════════════════════════════════════════════════════════════════
#  📣 РЕКЛАМА
# ══════════════════════════════════════════════════════════════════════════════

def _ads_kb() -> InlineKeyboardMarkup:
    ads = db.get_ads()
    rows = []
    for ad in ads:
        status = "✅" if ad["enabled"] else "⏸"
        rows.append([
            InlineKeyboardButton(
                text=f"{status} #{ad['id']} {ad['title']} ({ad['shows']} показов)",
                callback_data=f"admin:ad_detail:{ad['id']}"
            ),
        ])
    rows.append([InlineKeyboardButton(text="➕ Добавить объявление", callback_data="admin:ad_add")])
    rows += _back()
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "admin:ads")
async def admin_ads(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    every_n = db.get_setting("ad_every_n", "3")
    ads = db.get_ads()
    enabled_count = sum(1 for a in ads if a["enabled"])
    await callback.message.edit_text(
        f"📣 <b>Рекламные объявления</b>\n\n"
        f"Показ: каждые <b>{every_n}</b> загрузки\n"
        f"Активных: <b>{enabled_count}</b> из <b>{len(ads)}</b>\n\n"
        f"Выбери объявление для управления:",
        parse_mode="HTML",
        reply_markup=_ads_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:ad_detail:"))
async def admin_ad_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    ad_id = int(callback.data.split(":")[-1])
    ads = {a["id"]: a for a in db.get_ads()}
    ad  = ads.get(ad_id)
    if not ad:
        await callback.answer("Не найдено")
        return

    status = "✅ Активно" if ad["enabled"] else "⏸ На паузе"
    text = (
        f"📣 <b>Объявление #{ad['id']}</b>\n\n"
        f"Название: <b>{ad['title']}</b>\n"
        f"Статус: {status}\n"
        f"Показов: <b>{ad['shows']}</b>\n\n"
        f"Текст:\n{ad['text']}\n\n"
        + (f"Кнопка: <a href='{ad['btn_url']}'>{ad['btn_text']}</a>" if ad["btn_url"] else "Без кнопки")
    )
    toggle_label = "⏸ Поставить на паузу" if ad["enabled"] else "▶️ Включить"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_label, callback_data=f"admin:ad_toggle:{ad_id}")],
        [InlineKeyboardButton(text="🗑 Удалить",  callback_data=f"admin:ad_del:{ad_id}")],
        *_back("ads"),
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb,
                                     disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:ad_toggle:"))
async def admin_ad_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    ad_id = int(callback.data.split(":")[-1])
    db.toggle_ad(ad_id)
    await admin_ads(callback)


@router.callback_query(F.data.startswith("admin:ad_del:"))
async def admin_ad_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    ad_id = int(callback.data.split(":")[-1])
    db.delete_ad(ad_id)
    await callback.answer("✅ Удалено")
    await admin_ads(callback)


# Добавление объявления — диалог

@router.callback_query(F.data == "admin:ad_add")
async def admin_ad_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "📣 <b>Новое объявление</b>\n\n"
        "Шаг 1/3: Введи <b>название</b> объявления (только для тебя, в панели).",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=_back("ads")),
    )
    await state.set_state(AdminStates.ad_add_title)
    await callback.answer()


@router.message(AdminStates.ad_add_title)
async def admin_ad_add_title(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(ad_title=message.text.strip())
    await message.answer(
        "Шаг 2/3: Введи <b>текст объявления</b>.\n\n"
        "Поддерживается HTML: <code>&lt;b&gt;</code>, <code>&lt;i&gt;</code>, <code>&lt;a href&gt;</code>",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.ad_add_text)


@router.message(AdminStates.ad_add_text)
async def admin_ad_add_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(ad_text=message.text)
    await message.answer(
        "Шаг 3/3: Кнопка под объявлением?\n\n"
        "Формат: <code>Текст кнопки | https://url.com</code>\n"
        "Или <code>skip</code> — без кнопки.",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.ad_add_button)


@router.message(AdminStates.ad_add_button)
async def admin_ad_add_button(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    btn_text = btn_url = None
    text = message.text.strip()
    if text.lower() != "skip":
        parts = text.split("|", 1)
        if len(parts) == 2:
            btn_text = parts[0].strip()
            btn_url  = parts[1].strip()
        else:
            await message.answer("❌ Неверный формат. Попробуй ещё раз или напиши skip.")
            return

    db.add_ad(data["ad_title"], data["ad_text"], btn_text, btn_url)
    await state.clear()
    log.info(f"[admin] добавлено объявление '{data['ad_title']}'")
    await message.answer(
        f"✅ Объявление <b>{data['ad_title']}</b> создано и активно!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ К рекламе", callback_data="admin:ads")
        ]])
    )


# ══════════════════════════════════════════════════════════════════════════════
#  📬 РАССЫЛКИ
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:broadcasts")
async def admin_broadcasts(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    rows_data = db.list_broadcasts()
    status_icons = {"pending": "⏳", "sending": "📤", "done": "✅", "cancelled": "❌"}

    text = "📬 <b>Рассылки</b>\n\n"
    if rows_data:
        for r in rows_data:
            icon = status_icons.get(r["status"], "❓")
            text += (f"{icon} <b>#{r['id']}</b> [{r['target_lang']}] "
                     f"✓{r['sent']} ✗{r['failed']}\n"
                     f"   <i>{r['preview']}...</i>\n\n")
    else:
        text += "<i>Рассылок ещё не было.</i>"

    kb_rows = []
    # Кнопки отмены для pending рассылок
    for r in rows_data:
        if r["status"] == "pending":
            kb_rows.append([InlineKeyboardButton(
                text=f"❌ Отменить #{r['id']}",
                callback_data=f"admin:bc_cancel:{r['id']}"
            )])
    kb_rows.append([InlineKeyboardButton(text="✏️ Создать рассылку", callback_data="admin:bc_create")])
    kb_rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:broadcasts")])
    kb_rows += _back()

    await callback.message.edit_text(text, parse_mode="HTML",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:bc_cancel:"))
async def admin_bc_cancel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    bc_id = int(callback.data.split(":")[-1])
    db.cancel_broadcast(bc_id)
    await callback.answer(f"✅ Рассылка #{bc_id} отменена")
    await admin_broadcasts(callback)


# Создание рассылки — диалог из 4 шагов

@router.callback_query(F.data == "admin:bc_create")
async def admin_bc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "📬 <b>Новая рассылка</b>\n\n"
        "Шаг 1/4: Введи <b>текст сообщения</b>.\n\n"
        "Поддерживается HTML.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=_back("broadcasts")),
    )
    await state.set_state(AdminStates.bc_text)
    await callback.answer()


@router.message(AdminStates.bc_text)
async def admin_bc_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(bc_text=message.text)
    await message.answer(
        "Шаг 2/4: Кнопка?\n\n"
        "Формат: <code>Текст | https://url.com</code>\n"
        "Или <code>skip</code>.",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.bc_button)


@router.message(AdminStates.bc_button)
async def admin_bc_button(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    btn_text = btn_url = None
    text = message.text.strip()
    if text.lower() != "skip":
        parts = text.split("|", 1)
        if len(parts) == 2:
            btn_text = parts[0].strip()
            btn_url  = parts[1].strip()
        else:
            await message.answer("❌ Неверный формат. Попробуй ещё раз или skip.")
            return
    await state.update_data(bc_btn_text=btn_text, bc_btn_url=btn_url)
    s = db.stats()
    await message.answer(
        f"Шаг 3/4: Аудитория?\n\n"
        f"• <code>all</code> — все ({s['total']})\n"
        f"• <code>ru</code> — только RU ({s['ru']})\n"
        f"• <code>en</code> — только EN ({s['en']})",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.bc_lang)


@router.message(AdminStates.bc_lang)
async def admin_bc_lang(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    lang = message.text.strip().lower()
    if lang not in ("all", "ru", "en"):
        await message.answer("❌ Введи: all, ru или en")
        return
    await state.update_data(bc_lang=lang)
    await message.answer(
        "Шаг 4/4: Время отправки?\n\n"
        "• <code>now</code> — немедленно\n"
        "• <code>18:30</code> — сегодня в 18:30 МСК\n"
        "• <code>25.02 18:30</code> — конкретная дата МСК",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.bc_time)


@router.message(AdminStates.bc_time)
async def admin_bc_time(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    text = message.text.strip().lower()
    send_at = None

    if text != "now":
        msk = timezone(timedelta(hours=TZ_OFFSET))
        now_msk = datetime.now(msk)
        try:
            if re.match(r'^\d{2}:\d{2}$', text):
                h, m = map(int, text.split(":"))
                dt = now_msk.replace(hour=h, minute=m, second=0, microsecond=0)
                if dt < now_msk:
                    dt += timedelta(days=1)
            elif re.match(r'^\d{2}\.\d{2} \d{2}:\d{2}$', text):
                dt = datetime.strptime(text, "%d.%m %H:%M").replace(
                    year=now_msk.year, tzinfo=msk)
            else:
                await message.answer("❌ Неверный формат.")
                return
            send_at = dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            await message.answer("❌ Ошибка в дате.")
            return

    bc_id = db.create_broadcast(
        text=data["bc_text"],
        btn_text=data.get("bc_btn_text"),
        btn_url=data.get("bc_btn_url"),
        target_lang=data["bc_lang"],
        send_at=send_at,
    )
    await state.clear()

    users_count = len(db.all_user_ids(data["bc_lang"]))
    send_label = "немедленно" if send_at is None else f"в {text} МСК"
    log.info(f"[admin] рассылка #{bc_id} создана lang={data['bc_lang']} send_at={send_at}")

    await message.answer(
        f"✅ <b>Рассылка #{bc_id} создана</b>\n\n"
        f"👥 Получателей: <b>{users_count}</b>\n"
        f"⏰ Отправка: <b>{send_label}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ К рассылкам", callback_data="admin:broadcasts")
        ]])
    )


# ══════════════════════════════════════════════════════════════════════════════
#  👥 ПОЛЬЗОВАТЕЛИ
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "👥 <b>Управление пользователями</b>\n\n"
        "Введи <b>username, имя или ID</b> пользователя для поиска.\n\n"
        "Например: <code>@username</code> или <code>123456789</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=_back()),
    )
    await state.set_state(AdminStates.user_search)
    await callback.answer()


@router.message(AdminStates.user_search)
async def admin_user_search(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    query = message.text.strip().lstrip("@")
    users = db.search_users(query)
    await state.clear()

    if not users:
        await message.answer(
            "❌ Пользователи не найдены.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔍 Искать снова", callback_data="admin:users"),
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin:home"),
            ]])
        )
        return

    text = f"🔍 Найдено: <b>{len(users)}</b>\n\n"
    kb_rows = []
    for u in users:
        ban_icon = "🚫" if u["is_banned"] else "👤"
        uname = f"@{u['username']}" if u["username"] else "—"
        text += f"{ban_icon} <b>{u['first_name']}</b> ({uname}) · ID: <code>{u['user_id']}</code> · 📥{u['total_downloads']}\n"
        kb_rows.append([InlineKeyboardButton(
            text=f"{'🔓 Разбанить' if u['is_banned'] else '🚫 Забанить'} {u['first_name']}",
            callback_data=f"admin:user_ban:{u['user_id']}:{1 if not u['is_banned'] else 0}"
        )])

    kb_rows.append([InlineKeyboardButton(text="🔍 Искать снова", callback_data="admin:users")])
    kb_rows += _back()

    await message.answer(text, parse_mode="HTML",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data.startswith("admin:user_ban:"))
async def admin_user_ban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    user_id = int(parts[2])
    ban     = bool(int(parts[3]))
    db.ban_user(user_id, ban)
    action = "забанен 🚫" if ban else "разбанен ✅"
    log.info(f"[admin] user={user_id} {action}")
    await callback.answer(f"✅ Пользователь {action}")
    await admin_users(callback)


# ══════════════════════════════════════════════════════════════════════════════
#  ⚙️ НАСТРОЙКИ
# ══════════════════════════════════════════════════════════════════════════════

SETTINGS_META = {
    "ad_every_n":      ("📣 Реклама каждые N загрузок",  "0 = выключено"),
    "queue_workers":   ("⚙️ Параллельных загрузок",       "рекомендуется 3–10"),
    "cache_ttl_hours": ("💾 TTL кэша (часов)",            "0 = не кэшировать"),
    "sub_required":    ("🔒 Обязательная подписка",       "1 = вкл, 0 = выкл"),
}


@router.callback_query(F.data == "admin:settings")
async def admin_settings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    current = db.get_all_settings()
    text = "⚙️ <b>Настройки</b>\n\nНажми на параметр чтобы изменить:\n\n"
    rows = []
    for key, (label, hint) in SETTINGS_META.items():
        val = current.get(key, "—")
        text += f"• {label}: <b>{val}</b> <i>({hint})</i>\n"
        rows.append([InlineKeyboardButton(
            text=f"✏️ {label}: {val}",
            callback_data=f"admin:setting_edit:{key}"
        )])
    rows.append([InlineKeyboardButton(text="🗑 Очистить кэш", callback_data="admin:cache_clear")])
    rows += _back()

    await callback.message.edit_text(text, parse_mode="HTML",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:setting_edit:"))
async def admin_setting_edit_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    key   = callback.data.split(":")[-1]
    label, hint = SETTINGS_META.get(key, (key, ""))
    current = db.get_setting(key, "—")
    await callback.message.edit_text(
        f"⚙️ <b>{label}</b>\n\n"
        f"Текущее значение: <code>{current}</code>\n"
        f"<i>{hint}</i>\n\n"
        "Введи новое значение:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=_back("settings")),
    )
    await state.update_data(setting_key=key)
    await state.set_state(AdminStates.setting_edit)
    await callback.answer()


@router.message(AdminStates.setting_edit)
async def admin_setting_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data  = await state.get_data()
    key   = data.get("setting_key")
    value = message.text.strip()
    db.set_setting(key, value)
    await state.clear()
    log.info(f"[admin] setting {key}={value}")
    label = SETTINGS_META.get(key, (key,))[0]
    await message.answer(
        f"✅ <b>{label}</b> → <code>{value}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ К настройкам", callback_data="admin:settings")
        ]])
    )


@router.callback_query(F.data == "admin:cache_clear")
async def admin_cache_clear(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    db.cache_clear()
    log.info("[admin] кэш очищен")
    await callback.answer("✅ Кэш очищен", show_alert=True)
    await admin_settings(callback)
