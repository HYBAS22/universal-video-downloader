"""
database.py — все операции с SQLite.
Настройки бота хранятся в таблице settings и меняются через админ-панель без перезапуска.
"""

import sqlite3
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from config import DB_PATH

Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as db:
        db.executescript("""
        -- Пользователи
        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT,
            first_name      TEXT,
            lang            TEXT DEFAULT 'ru',
            joined_at       TEXT DEFAULT (date('now')),
            total_downloads INTEGER DEFAULT 0,
            is_banned       INTEGER DEFAULT 0,
            is_blocked      INTEGER DEFAULT 0
        );

        -- Глобальные настройки (key-value, редактируются из панели)
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        -- Каналы для обязательной подписки
        CREATE TABLE IF NOT EXISTS sub_channels (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id  TEXT UNIQUE,
            title       TEXT,
            url         TEXT,
            enabled     INTEGER DEFAULT 1
        );

        -- Рекламные объявления
        CREATE TABLE IF NOT EXISTS ads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT,
            text        TEXT,
            btn_text    TEXT,
            btn_url     TEXT,
            enabled     INTEGER DEFAULT 1,
            shows       INTEGER DEFAULT 0,
            clicks      INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- Рассылки
        CREATE TABLE IF NOT EXISTS broadcasts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            text        TEXT,
            btn_text    TEXT,
            btn_url     TEXT,
            target_lang TEXT DEFAULT 'all',
            send_at     TEXT,
            status      TEXT DEFAULT 'pending',
            sent        INTEGER DEFAULT 0,
            failed      INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- История загрузок
        CREATE TABLE IF NOT EXISTS download_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            platform    TEXT,
            url         TEXT,
            quality     TEXT,
            size_mb     REAL,
            ts          TEXT DEFAULT (datetime('now'))
        );

        -- Кэш file_id
        CREATE TABLE IF NOT EXISTS file_cache (
            url_hash    TEXT PRIMARY KEY,
            file_id     TEXT,
            is_audio    INTEGER DEFAULT 0,
            expires_at  TEXT
        );
        """)
        _seed_defaults(db)


def _seed_defaults(db: sqlite3.Connection):
    defaults = {
        "ad_every_n":       "3", # реклама каждые N загрузок
        "queue_workers":    "5",
        "cache_ttl_hours":  "24",
        "sub_required":     "1", # 0/1
    }
    for k, v in defaults.items():
        db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))


# Настройки

def get_setting(key: str, default=None) -> str | None:
    with conn() as db:
        row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    with conn() as db:
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

def get_all_settings() -> dict:
    with conn() as db:
        rows = db.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


# Юзеры

def upsert_user(user_id: int, username: str | None, first_name: str | None):
    with conn() as db:
        db.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                is_blocked=0
        """, (user_id, username, first_name))

def get_user(user_id: int) -> sqlite3.Row | None:
    with conn() as db:
        return db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()

def get_lang(user_id: int) -> str:
    row = get_user(user_id)
    return row["lang"] if row else "ru"

def set_lang(user_id: int, lang: str):
    with conn() as db:
        db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))

def ban_user(user_id: int, value: bool = True):
    with conn() as db:
        db.execute("UPDATE users SET is_banned=? WHERE user_id=?", (int(value), user_id))

def mark_blocked(user_id: int):
    with conn() as db:
        db.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (user_id,))

def increment_downloads(user_id: int):
    with conn() as db:
        db.execute("UPDATE users SET total_downloads=total_downloads+1 WHERE user_id=?", (user_id,))

def all_user_ids(lang: str = "all") -> list[int]:
    with conn() as db:
        if lang == "all":
            rows = db.execute("SELECT user_id FROM users WHERE is_blocked=0 AND is_banned=0").fetchall()
        else:
            rows = db.execute(
                "SELECT user_id FROM users WHERE is_blocked=0 AND is_banned=0 AND lang=?", (lang,)
            ).fetchall()
    return [r["user_id"] for r in rows]

def search_users(query: str) -> list:
    q = f"%{query}%"
    with conn() as db:
        return db.execute(
            "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ? OR CAST(user_id AS TEXT) LIKE ? LIMIT 10",
            (q, q, q)
        ).fetchall()

def stats() -> dict:
    today = str(date.today())
    with conn() as db:
        total    = db.execute("SELECT COUNT(*) FROM users WHERE is_blocked=0 AND is_banned=0").fetchone()[0]
        ru       = db.execute("SELECT COUNT(*) FROM users WHERE lang='ru' AND is_blocked=0").fetchone()[0]
        en       = db.execute("SELECT COUNT(*) FROM users WHERE lang='en' AND is_blocked=0").fetchone()[0]
        banned   = db.execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0]
        total_dl = db.execute("SELECT SUM(total_downloads) FROM users").fetchone()[0] or 0
        today_dl = db.execute(
            "SELECT COUNT(*) FROM download_history WHERE ts LIKE ?", (f"{today}%",)
        ).fetchone()[0]
        new_today = db.execute(
            "SELECT COUNT(*) FROM users WHERE joined_at=?", (today,)
        ).fetchone()[0]
    return dict(total=total, ru=ru, en=en, banned=banned,
                total_dl=total_dl, today_dl=today_dl, new_today=new_today)


# Подканалы

def get_channels(enabled_only: bool = False) -> list:
    with conn() as db:
        if enabled_only:
            return db.execute("SELECT * FROM sub_channels WHERE enabled=1").fetchall()
        return db.execute("SELECT * FROM sub_channels").fetchall()

def add_channel(channel_id: str, title: str, url: str):
    with conn() as db:
        db.execute(
            "INSERT OR REPLACE INTO sub_channels (channel_id, title, url) VALUES (?, ?, ?)",
            (channel_id, title, url)
        )

def toggle_channel(row_id: int):
    with conn() as db:
        db.execute("UPDATE sub_channels SET enabled = 1-enabled WHERE id=?", (row_id,))

def delete_channel(row_id: int):
    with conn() as db:
        db.execute("DELETE FROM sub_channels WHERE id=?", (row_id,))


# Реклама

def get_ads(enabled_only: bool = False) -> list:
    with conn() as db:
        if enabled_only:
            return db.execute("SELECT * FROM ads WHERE enabled=1").fetchall()
        return db.execute("SELECT * FROM ads ORDER BY id DESC").fetchall()

def add_ad(title: str, text: str, btn_text: str | None, btn_url: str | None):
    with conn() as db:
        db.execute(
            "INSERT INTO ads (title, text, btn_text, btn_url) VALUES (?, ?, ?, ?)",
            (title, text, btn_text, btn_url)
        )

def toggle_ad(ad_id: int):
    with conn() as db:
        db.execute("UPDATE ads SET enabled = 1-enabled WHERE id=?", (ad_id,))

def delete_ad(ad_id: int):
    with conn() as db:
        db.execute("DELETE FROM ads WHERE id=?", (ad_id,))

def increment_ad_shows(ad_id: int):
    with conn() as db:
        db.execute("UPDATE ads SET shows=shows+1 WHERE id=?", (ad_id,))


# Рассылка

def create_broadcast(text: str, btn_text: str | None, btn_url: str | None,
                     target_lang: str, send_at: str | None) -> int:
    with conn() as db:
        cur = db.execute(
            "INSERT INTO broadcasts (text, btn_text, btn_url, target_lang, send_at) VALUES (?,?,?,?,?)",
            (text, btn_text, btn_url, target_lang, send_at)
        )
        return cur.lastrowid

def get_pending_broadcasts() -> list:
    now = datetime.utcnow().isoformat()
    with conn() as db:
        return db.execute(
            "SELECT * FROM broadcasts WHERE status='pending' AND (send_at IS NULL OR send_at<=?)", (now,)
        ).fetchall()

def update_broadcast(bc_id: int, sent: int, failed: int, status: str = "done"):
    with conn() as db:
        db.execute("UPDATE broadcasts SET status=?, sent=?, failed=? WHERE id=?",
                   (status, sent, failed, bc_id))

def cancel_broadcast(bc_id: int):
    with conn() as db:
        db.execute("UPDATE broadcasts SET status='cancelled' WHERE id=? AND status='pending'", (bc_id,))

def list_broadcasts(limit: int = 10) -> list:
    with conn() as db:
        return db.execute(
            "SELECT *, substr(text,1,50) as preview FROM broadcasts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


# История

def add_history(user_id: int, platform: str, url: str, quality: str, size_mb: float):
    with conn() as db:
        db.execute(
            "INSERT INTO download_history (user_id, platform, url, quality, size_mb) VALUES (?,?,?,?,?)",
            (user_id, platform, url, quality, round(size_mb, 2))
        )
        db.execute("""
            DELETE FROM download_history WHERE user_id=? AND id NOT IN (
                SELECT id FROM download_history WHERE user_id=? ORDER BY id DESC LIMIT 20
            )
        """, (user_id, user_id))

def get_history(user_id: int, limit: int = 10) -> list:
    with conn() as db:
        return db.execute(
            "SELECT * FROM download_history WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()

def get_daily_count(user_id: int) -> int:
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d") # UTC
    with conn() as db:
        return db.execute(
            "SELECT COUNT(*) FROM download_history WHERE user_id=? AND ts LIKE ?",
            (user_id, f"{today_utc}%")
        ).fetchone()[0]


# Кэш

def cache_get(url: str) -> tuple[str, bool] | None:
    key = str(hash(url))
    now = datetime.utcnow().isoformat()
    with conn() as db:
        row = db.execute(
            "SELECT file_id, is_audio FROM file_cache WHERE url_hash=? AND expires_at>?", (key, now)
        ).fetchone()
    return (row["file_id"], bool(row["is_audio"])) if row else None

def cache_set(url: str, file_id: str, is_audio: bool = False):
    key = str(hash(url))
    ttl = int(get_setting("cache_ttl_hours", "24"))
    exp = (datetime.utcnow() + timedelta(hours=ttl)).isoformat()
    with conn() as db:
        db.execute("""
            INSERT INTO file_cache (url_hash, file_id, is_audio, expires_at) VALUES (?,?,?,?)
            ON CONFLICT(url_hash) DO UPDATE SET file_id=excluded.file_id, expires_at=excluded.expires_at
        """, (key, file_id, int(is_audio), exp))

def cache_clear():
    with conn() as db:
        db.execute("DELETE FROM file_cache")
