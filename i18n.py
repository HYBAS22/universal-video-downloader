"""i18n.py — локализация."""

import database as db

STRINGS = {
    "ru": {
        "start":          "👋 <b>Привет, {name}!</b>\n\n🎥 Скачиваю видео с популярных платформ.\n\n<b>Платформы:</b>\n{platforms}\n\n📎 Просто отправь ссылку!",
        "platforms":      "• TikTok\n• YouTube (включая Shorts)\n• Instagram Reels / Posts\n• Twitter / X\n• VK\n• и любые другие сайты с видео",
        "send_link":      "📎 <b>Отправь ссылку на видео</b>\n\nПлатформы:\n{platforms}",
        "link_ok":        "✅ Ссылка получена!\n🌐 Платформа: <b>{platform}</b>\n\n🎬 Выбери качество:",
        "bad_link":       "❌ Не нашёл ссылку в сообщении.",
        "bad_platform":   "❌ <b>Неподдерживаемая платформа.</b>\n\n{platforms}",
        "loading":        "⏳ <b>Загружаю...</b>\n\n🌐 {platform}\n🎬 {quality}\n\nМожет занять 10–60 сек.",
        "queue_wait":     "⏳ <b>Ты в очереди</b> — позиция <b>{pos}</b>.\n\nСкоро начнём!",
        "sending":        "📤 <b>Отправляю...</b>",
        "done":           "✅ Готово!\n🌐 {platform}  ·  🎬 {quality}  ·  💾 {size} МБ",
        "too_big":        "❌ <b>Файл слишком большой ({size} МБ)</b>\n\nTelegram принимает максимум 50 МБ. Попробуй SD.",
        "dl_fail":        "❌ <b>Не удалось скачать</b>\n\nПричина: {reason}\n\n💡 Попробуй другое качество.",
        "send_fail":      "❌ <b>Ошибка при отправке.</b> Попробуй другое качество.",
        "cache_hit":      "⚡ <b>Из кэша!</b>\n🌐 {platform}  ·  🎬 {quality}",
        "banned":         "🚫 Ты заблокирован в этом боте.",
        # ---- ИСПРАВЛЕНО: убрано inline-выражение ----
        "sub_req_one":    "🔒 <b>Подпишись на канал, чтобы пользоваться ботом.</b>\n\n{channels}\n\nПосле подписки нажми кнопку ниже.",
        "sub_req_many":   "🔒 <b>Подпишись на каналы, чтобы пользоваться ботом.</b>\n\n{channels}\n\nПосле подписки нажми кнопку ниже.",
        "sub_ok":         "✅ Подписка подтверждена! Отправляй ссылки.",
        "sub_no":         "❌ Ты ещё не подписан на все каналы!",
        "cancel":         "❌ Отменено.",
        "history_empty":  "📭 История пуста.",
        "history_title":  "📋 <b>Последние загрузки:</b>\n\n",
        "help":           "📖 <b>Как пользоваться:</b>\n\n1️⃣ Отправь ссылку\n2️⃣ Выбери качество\n3️⃣ Получи видео\n\n<b>Платформы:</b>\n{platforms}\n\n⚠️ Telegram ограничивает файлы до <b>50 МБ</b>.",
        "queue_timeout":  "⏰ Слишком долгое ожидание. Попробуй позже.",
        # кнопки
        "btn_download":   "📥 Скачать видео",
        "btn_help":       "ℹ️ Помощь",
        "btn_history":    "🕓 История",
        "btn_about":      "📊 О боте",
        "btn_lang":       "🌐 English",
        "btn_hd":         "🎬 HD (до 1080p)",
        "btn_sd":         "📱 SD (до 480p)",
        "btn_wm":         "💧 С водяным знаком",
        "btn_audio":      "🎵 Только аудио (.m4a)",
        "btn_cancel":     "❌ Отмена",
        "btn_subscribed": "✅ Я подписался",
        # ---- Обрезка видео ----
        "btn_trim":       "✂️ Обрезать видео",
        "trim_ask_start":  "⏱️ <b>Отправь время начала обрезки</b>\n\nФормат: <code>MM:SS</code> или секунды\nПример: <code>00:15</code> или <code>15</code>",
        "trim_ask_end":    "⏱️ <b>Отправь время окончания обрезки</b>\n\nФормат: <code>MM:SS</code> или секунды\nПример: <code>00:45</code> или <code>45</code>",
        "trim_format_err": "❌ <b>Неверный формат.</b>\n\nИспользуй: <code>MM:SS</code> (00:15) или просто секунды (15)",
        "trim_logic_err":  "❌ <b>Ошибка:</b> время окончания должно быть больше времени начала.",
        "trim_loading":    "✂️ <b>Обрезаю видео...</b>\n\nЭто может занять время...",
        "trim_fail":       "❌ <b>Не удалось обрезать видео</b>\n\nПричина: {reason}",
        "trim_done":       "✅ <b>Видео обрезано!</b>\n🎬 {quality}  ·  💾 {size} МБ",
    },
    "en": {
        "start":          "👋 <b>Hey, {name}!</b>\n\n🎥 I download videos from popular platforms.\n\n<b>Platforms:</b>\n{platforms}\n\n📎 Send me a link!",
        "platforms":      "• TikTok\n• YouTube (incl. Shorts)\n• Instagram Reels / Posts\n• Twitter / X\n• VK\n• and any other video site",
        "send_link":      "📎 <b>Send a video link</b>\n\nPlatforms:\n{platforms}",
        "link_ok":        "✅ Link received!\n🌐 Platform: <b>{platform}</b>\n\n🎬 Choose quality:",
        "bad_link":       "❌ No link found in your message.",
        "bad_platform":   "❌ <b>Unsupported platform.</b>\n\n{platforms}",
        "loading":        "⏳ <b>Downloading...</b>\n\n🌐 {platform}\n🎬 {quality}\n\nMay take 10–60 sec.",
        "queue_wait":     "⏳ <b>You're in queue</b> — position <b>{pos}</b>.\n\nStarting soon!",
        "sending":        "📤 <b>Sending...</b>",
        "done":           "✅ Done!\n🌐 {platform}  ·  🎬 {quality}  ·  💾 {size} MB",
        "too_big":        "❌ <b>File too large ({size} MB)</b>\n\nTelegram limit is 50 MB. Try SD.",
        "dl_fail":        "❌ <b>Download failed</b>\n\nReason: {reason}\n\n💡 Try another quality.",
        "send_fail":      "❌ <b>Failed to send.</b> Try another quality.",
        "cache_hit":      "⚡ <b>From cache!</b>\n🌐 {platform}  ·  🎬 {quality}",
        "banned":         "🚫 You are banned from this bot.",
        # ---- ИСПРАВЛЕНО ----
        "sub_req_one":    "🔒 <b>Subscribe to the channel to continue:</b>\n\n{channels}\n\nPress the button below after subscribing.",
        "sub_req_many":   "🔒 <b>Subscribe to the channels to continue:</b>\n\n{channels}\n\nPress the button below after subscribing.",
        "sub_ok":         "✅ Subscription confirmed! Send links anytime.",
        "sub_no":         "❌ You haven't subscribed to all channels yet!",
        "cancel":         "❌ Cancelled.",
        "history_empty":  "📭 No downloads yet.",
        "history_title":  "📋 <b>Recent downloads:</b>\n\n",
        "help":           "📖 <b>How to use:</b>\n\n1️⃣ Send a link\n2️⃣ Choose quality\n3️⃣ Get your video\n\n<b>Platforms:</b>\n{platforms}\n\n⚠️ Telegram limits files to <b>50 MB</b>.",
        "queue_timeout":  "⏰ Wait time exceeded. Try again later.",
        "btn_download":   "📥 Download video",
        "btn_help":       "ℹ️ Help",
        "btn_history":    "🕓 History",
        "btn_about":      "📊 About",
        "btn_lang":       "🌐 Русский",
        "btn_hd":         "🎬 HD (up to 1080p)",
        "btn_sd":         "📱 SD (up to 480p)",
        "btn_wm":         "💧 With watermark",
        "btn_audio":      "🎵 Audio only (.m4a)",
        "btn_cancel":     "❌ Cancel",
        "btn_subscribed": "✅ I subscribed",
        # ---- Video trimming ----
        "btn_trim":       "✂️ Trim video",
        "trim_ask_start":  "⏱️ <b>Send trim start time</b>\n\nFormat: <code>MM:SS</code> or seconds\nExample: <code>00:15</code> or <code>15</code>",
        "trim_ask_end":    "⏱️ <b>Send trim end time</b>\n\nFormat: <code>MM:SS</code> or seconds\nExample: <code>00:45</code> or <code>45</code>",
        "trim_format_err": "❌ <b>Invalid format.</b>\n\nUse: <code>MM:SS</code> (00:15) or just seconds (15)",
        "trim_logic_err":  "❌ <b>Error:</b> end time must be greater than start time.",
        "trim_loading":    "✂️ <b>Trimming video...</b>\n\nThis may take a moment...",
        "trim_fail":       "❌ <b>Failed to trim video</b>\n\nReason: {reason}",
        "trim_done":       "✅ <b>Video trimmed!</b>\n🎬 {quality}  ·  💾 {size} MB",
    },
}


def t(user_id: int, key: str, **kw) -> str:
    lang = db.get_lang(user_id)
    s = STRINGS.get(lang, STRINGS["ru"])
    text = s.get(key, STRINGS["ru"].get(key, f"[{key}]"))
    return text.format(**kw) if kw else text


def t_sub_req(user_id: int, channels_text: str, count: int) -> str:
    key = "sub_req_one" if count == 1 else "sub_req_many"
    return t(user_id, key, channels=channels_text)