"""
Database layer for the Shopping Assistant.

Handles two kinds of persistence:
1. User preferences (remembered across sessions, e.g. "always wants black",
   "budget under $150", "prefers wireless")
2. Tracked products + price history (for price-drop alerts)

Uses plain SQLite so there's zero setup — the DB file is created
automatically on first run.
"""

import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

DB_PATH = "assistant.db"


def init_db():
    """Create tables if they don't already exist. Safe to call every run."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, key)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tracked_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                search_query TEXT NOT NULL,
                target_price REAL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                price REAL,
                source_url TEXT,
                raw_note TEXT,
                checked_at TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES tracked_products (id)
            )
        """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------- Preferences ----------

def set_preference(user_id: str, key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO preferences (user_id, key, value, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value,
                                                        updated_at=excluded.updated_at""",
            (user_id, key, value, datetime.utcnow().isoformat()),
        )


def get_preferences(user_id: str) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT key, value FROM preferences WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {row["key"]: row["value"] for row in rows}


def delete_preference(user_id: str, key: str):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM preferences WHERE user_id = ? AND key = ?", (user_id, key)
        )


# ---------- Tracked products ----------

def add_tracked_product(user_id: str, name: str, search_query: str, target_price: float = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO tracked_products (user_id, name, search_query, target_price, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, name, search_query, target_price, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def list_tracked_products(user_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tracked_products WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def remove_tracked_product(product_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM price_checks WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM tracked_products WHERE id = ?", (product_id,))


def record_price_check(product_id: int, price: float, source_url: str, raw_note: str = ""):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO price_checks (product_id, price, source_url, raw_note, checked_at)
               VALUES (?, ?, ?, ?, ?)""",
            (product_id, price, source_url, raw_note, datetime.utcnow().isoformat()),
        )


def get_price_history(product_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM price_checks WHERE product_id = ? ORDER BY checked_at ASC",
            (product_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_lowest_price(product_id: int):
    history = get_price_history(product_id)
    prices = [h["price"] for h in history if h["price"] is not None]
    return min(prices) if prices else None
