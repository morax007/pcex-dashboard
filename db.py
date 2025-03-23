# db.py
import sqlite3
import uuid
from datetime import datetime

def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id TEXT PRIMARY KEY,
            token TEXT,
            is_connected INTEGER DEFAULT 0,
            trial_start TEXT,
            is_subscribed INTEGER DEFAULT 0,
            plan TEXT,
            subscription_expiry TEXT,
            pcex_username TEXT,
            pcex_password TEXT,
            last_active TEXT
        )
    """)
    conn.commit()
    conn.close()

def set_trial_start(tg_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT trial_start FROM users WHERE telegram_id = ?", (tg_id,))
    result = c.fetchone()
    if result and result[0] is None:
        c.execute("UPDATE users SET trial_start = ? WHERE telegram_id = ?", (datetime.utcnow().isoformat(), tg_id))
    elif not result:
        # User record might not exist yet
        c.execute("INSERT INTO users (telegram_id, trial_start) VALUES (?, ?)", (tg_id, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def generate_token():
    return str(uuid.uuid4())

def create_or_update_user(telegram_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    token = generate_token()
    c.execute("""
        INSERT INTO users (telegram_id, token, is_connected, created_at)
        VALUES (?, ?, 0, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET token = excluded.token
    """, (telegram_id, token, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return token

def get_user(telegram_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    user = c.fetchone()
    conn.close()
    return user



