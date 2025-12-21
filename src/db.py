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
        "CREATE TABLE IF NOT EXISTS notes ("
        "  note_id INTEGER PRIMARY KEY, chat_id INTEGER UNIQUE NOT NULL, note TEXT,"
        "  FOREIGN KEY (chat_id) REFERENCES chat_history(chat_id)"
        ")"
    )


@transaction
def insert_chat(cur: sqlite3.Cursor, messages: list[dict[str, str]]):
    cur.execute(
        "INSERT INTO chat_history (messages) VALUES (jsonb(?))",
        (json.dumps(messages),),
    )


@transaction
def insert_note(cur: sqlite3.Cursor, chat_id: int, note: str):
    cur.execute(
        "INSERT INTO summaries (chat_id, note) VALUES (?, ?)",
        (chat_id, note),
    )


# in general, I am preferring to defer JSON deserialization
# because otherwise we have cases where we deserialize than immediately serialize
# when we pass to the LLM
def get_chat(chat_id: int) -> str:
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


def get_user_chats(chat_id: int) -> str:
    cur = con.cursor()
    try:
        cur.execute(
            "SELECT m.value->>'content' FROM chat_history c, json_each(c.messages) m"
            " WHERE c.chat_id = ? AND m.value->>'role' = 'user' AND m.key != 0"
            " ORDER BY m.key",
            chat_id,
        )
        return cur.fetchall()
    finally:
        cur.close()


def get_final_chat(chat_id: int) -> str:
    cur = con.cursor()
    try:
        cur.execute(
            "SELECT m.value FROM chat_history c, json_each(c.messages) m"
            " WHERE c.chat_id = ? ORDER BY m.key DESC LIMIT 1",
            chat_id,
        )
        result = cur.fetchone()
        try:
            result = result[0]
        except TypeError:
            raise ValueError("Chat ID not found") from None
        return result
    finally:
        cur.close()


def get_random_chat_notes(n: int):
    cur = con.cursor()
    try:
        cur.execute(
            "SELECT chat_id, note FROM notes ORDER BY random() LIMIT ?",
            (n,),
        )
        return cur.fetchall()
    finally:
        cur.close()
