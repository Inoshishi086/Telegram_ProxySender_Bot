import sqlite3
from datetime import datetime, timezone

DB = "proxies.db"


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_connection():
    return sqlite3.connect(DB)


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proxies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proxy_url TEXT UNIQUE NOT NULL,
            proxy_type TEXT NOT NULL,
            server TEXT NOT NULL,
            port INTEGER NOT NULL,
            operator TEXT DEFAULT 'unknown',
            ping_ms INTEGER DEFAULT 9999,
            is_active BOOLEAN DEFAULT 1,
            fail_count INTEGER DEFAULT 0,
            last_checked TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def insert_proxy(proxy_url, proxy_type, server, port, operator="unknown"):
    timestamp = now_str()
    conn = get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO proxies
           (proxy_url, proxy_type, server, port, operator, last_checked, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (proxy_url, proxy_type, server, port, operator, timestamp, timestamp)
    )
    conn.commit()
    conn.close()


def update_ping(proxy_url, ping_ms):
    timestamp = now_str()
    conn = get_connection()
    conn.execute(
        "UPDATE proxies SET ping_ms = ?, last_checked = ? WHERE proxy_url = ?",
        (ping_ms, timestamp, proxy_url)
    )
    conn.commit()
    conn.close()


def deactivate_proxy(proxy_url):
    timestamp = now_str()
    conn = get_connection()
    conn.execute(
        "UPDATE proxies SET is_active = 0, last_checked = ? WHERE proxy_url = ?",
        (timestamp, proxy_url)
    )
    conn.commit()
    conn.close()


def delete_proxy(proxy_url):
    conn = get_connection()
    conn.execute("DELETE FROM proxies WHERE proxy_url = ?", (proxy_url,))
    conn.commit()
    conn.close()


def get_best_proxy(operator, proxy_type):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM proxies WHERE is_active = 1 AND proxy_type = ? AND operator = ? ORDER BY ping_ms ASC LIMIT 1",
        (proxy_type, operator)
    )
    row = cursor.fetchone()
    conn.close()
    return row


def get_all_active_proxies(limit=10):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM proxies WHERE is_active = 1 ORDER BY last_checked ASC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows