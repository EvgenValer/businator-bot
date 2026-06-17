import sqlite3
from datetime import datetime, timedelta

DB = "beads.db"

def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            full_name TEXT,
            joined_at TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS beads (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            added_at TEXT,
            note TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER,
            group_id INTEGER,
            UNIQUE(telegram_id, group_id)
        )""")
        try:
            con.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
        except:
            pass

def register_user(telegram_id, username, full_name, group_id=None):
    with sqlite3.connect(DB) as con:
        con.execute("""INSERT INTO users (telegram_id, username, full_name, joined_at)
            VALUES (?,?,?,?)
            ON CONFLICT(telegram_id) DO UPDATE SET full_name=?, username=?""",
            (telegram_id, username, full_name, datetime.now().isoformat(), full_name, username))
        if group_id:
            con.execute("INSERT OR IGNORE INTO group_members (telegram_id, group_id) VALUES (?,?)",
                        (telegram_id, group_id))

def add_beads(telegram_id, count=1):
    with sqlite3.connect(DB) as con:
        row = con.execute("SELECT id FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
        if not row:
            return False
        for _ in range(count):
            con.execute("INSERT INTO beads (user_id, added_at) VALUES (?,?)",
                        (row[0], datetime.now().isoformat()))
        return True

def get_stats(telegram_id, days=None):
    with sqlite3.connect(DB) as con:
        uid = con.execute("SELECT id FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
        if not uid:
            return None
        if days:
            since = (datetime.now() - timedelta(days=days)).isoformat()
            count = con.execute("SELECT COUNT(*) FROM beads WHERE user_id=? AND added_at>=?",
                                (uid[0], since)).fetchone()[0]
        else:
            count = con.execute("SELECT COUNT(*) FROM beads WHERE user_id=?", (uid[0],)).fetchone()[0]
        return count

def get_group_stats(group_id, days=None):
    with sqlite3.connect(DB) as con:
        if days:
            since = (datetime.now() - timedelta(days=days)).isoformat()
            rows = con.execute("""
                SELECT COALESCE(u.full_name, u.username), COUNT(b.id) as cnt
                FROM users u
                JOIN group_members gm ON gm.telegram_id = u.telegram_id
                LEFT JOIN beads b ON u.id = b.user_id AND b.added_at >= ?
                WHERE gm.group_id = ?
                GROUP BY u.id ORDER BY cnt ASC
            """, (since, group_id)).fetchall()
        else:
            rows = con.execute("""
                SELECT COALESCE(u.full_name, u.username), COUNT(b.id) as cnt
                FROM users u
                JOIN group_members gm ON gm.telegram_id = u.telegram_id
                LEFT JOIN beads b ON u.id = b.user_id
                WHERE gm.group_id = ?
                GROUP BY u.id ORDER BY cnt ASC
            """, (group_id,)).fetchall()
        return rows

def get_user_groups(telegram_id):
    with sqlite3.connect(DB) as con:
        rows = con.execute("SELECT group_id FROM group_members WHERE telegram_id=?",
                           (telegram_id,)).fetchall()
        return [r[0] for r in rows]

def get_user_full_name(telegram_id):
    with sqlite3.connect(DB) as con:
        row = con.execute("SELECT COALESCE(full_name, username) FROM users WHERE telegram_id=?",
                          (telegram_id,)).fetchone()
        return row[0] if row else None

def reset_user(telegram_id):
    with sqlite3.connect(DB) as con:
        uid = con.execute("SELECT id FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
        if not uid:
            return False
        con.execute("DELETE FROM beads WHERE user_id=?", (uid[0],))
        return True

def leave_group(telegram_id, group_id):
    with sqlite3.connect(DB) as con:
        con.execute("DELETE FROM group_members WHERE telegram_id=? AND group_id=?",
                    (telegram_id, group_id))
        return True

def get_all_groups():
    with sqlite3.connect(DB) as con:
        rows = con.execute("SELECT DISTINCT group_id FROM group_members").fetchall()
        return [r[0] for r in rows]