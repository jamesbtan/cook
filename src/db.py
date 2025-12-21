import sqlite3
import json
from functools import wraps

con = sqlite3.connect("persist.db")
# set autocommit to True initially
# when False, a transaction is immediately begun,
# but foreign_keys pragma can only apply outside transaction
# immediately disable autocommit after enabling foreign keys
con = sqlite3.connect("persist.db", autocommit=True)
con.execute("PRAGMA foreign_keys = ON")
con.autocommit = False
con.row_factory = sqlite3.Row


def transaction(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        cur = con.cursor()
        try:
            res = f(cur, *args, **kwargs)
            con.commit()
            return res
        except Exception:
            con.rollback()
            raise
        finally:
            cur.close()

    return wrapper


@transaction
def initialize(cur: sqlite3.Cursor):
    cur.execute(
        "CREATE TABLE IF NOT EXISTS chat_history ("
        "  chat_id INTEGER PRIMARY KEY, messages BLOB NOT NULL"
        ")"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS summaries ("
        "  summary_id INTEGER PRIMARY KEY, chat_id INTEGER UNIQUE NOT NULL,"
        "  likes TEXT, dislikes TEXT,"
        "  FOREIGN KEY (chat_id) REFERENCES chat_history(chat_id)"
        ")"
    )


@transaction
def insert_chat(cur: sqlite3.Cursor, messages: list[str]):
    cur.execute(
        "INSERT INTO chat_history (messages) VALUES (jsonb(?))",
        (json.dumps(messages),),
    )


@transaction
def insert_summary(cur: sqlite3.Cursor, chat_id: int, summary):
    cur.execute(
        "INSERT INTO summaries (chat_id, likes, dislikes) VALUES (?, ?, ?)",
        (
            chat_id,
            summary.likes,
            summary.dislikes,
        ),
    )


def get_chat(chat_id: int):
    cur = con.cursor()
    try:
        cur.execute(
            "SELECT json(messages) FROM chat_history WHERE chat_id = ?", chat_id
        )
        result = cur.fetchone()
        try:
            result = result[0]
        except TypeError:
            raise ValueError("Chat ID not found") from None
        return result
    finally:
        cur.close()


def get_random_chat_summaries(n: int):
    cur = con.cursor()
    try:
        cur.execute(
            "SELECT chat_id, likes, dislikes FROM summaries ORDER BY random() LIMIT ?",
            (n,),
        )
        return cur.fetchall()
    finally:
        cur.close()
