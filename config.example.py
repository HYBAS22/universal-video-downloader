"""
config.py — только статические константы (токен, пути).
Всё остальное (реклама, каналы, настройки) — в БД через админ-панель.
"""

BOT_TOKEN    = ""
ADMIN_IDS    = [] # список ID администраторов
DOWNLOAD_DIR = "downloads"
DB_PATH      = "data/bot.db"
LOG_DIR      = "logs"
MAX_FILE_MB  = 50
TZ_OFFSET    = 3 # UTC+3 (МСК)