from functools import wraps
from typing import (
    Callable,
    Concatenate,
    ParamSpec,
    TypedDict,
    TypeVar,
)
import json
import sqlite3

con = sqlite3.connect("persist.db")
# set autocommit to True initially
# when False, a transaction is immediately begun,
# but foreign_keys pragma can only apply outside transaction
# immediately disable autocommit after enabling foreign keys
con = sqlite3.connect("persist.db", autocommit=True)
con.execute("PRAGMA foreign_keys = ON")
con.autocommit = False


def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


con.row_factory = dict_factory


P = ParamSpec("P")
R = TypeVar("R")


def transaction(
    f: Callable[Concatenate[sqlite3.Cursor, P], R],
) -> Callable[P, R]:
    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
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


def newest_chat_id(
    f: Callable[Concatenate[int, P], R],
) -> Callable[Concatenate[int | None, P], R]:
    @wraps(f)
    def wrapper(chat_id: int | None, *args, **kwargs):
        if chat_id is None:
            chat_id = get_newest_chat_id()
        return f(chat_id, *args, **kwargs)

    return wrapper


def get_newest_chat_id() -> int:
    cur = con.cursor()
    try:
        cur.execute("SELECT chat_id FROM chat_history ORDER BY created_at DESC LIMIT 1")
        result = cur.fetchone()
        try:
            result = result["chat_id"]
        except TypeError:
            raise ValueError("No chats found")
        return result
    finally:
        cur.close()


@transaction
def initialize(cur: sqlite3.Cursor):
    cur.execute(
        "CREATE TABLE IF NOT EXISTS chat_history ("
        " chat_id INTEGER PRIMARY KEY, messages BLOB NOT NULL, created_at TEXT NOT NULL"
        ")"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS notes ("
        " note_id INTEGER PRIMARY KEY, chat_id INTEGER UNIQUE NOT NULL,"
        " note TEXT NOT NULL, created_at TEXT NOT NULL,"
        " FOREIGN KEY (chat_id) REFERENCES chat_history(chat_id)"
        ")"
    )


@transaction
def insert_chat(cur: sqlite3.Cursor, messages: list[dict[str, str]]):
    cur.execute(
        "INSERT INTO chat_history (messages, created_at) VALUES (jsonb(?), datetime('now'))",
        (json.dumps(messages),),
    )


@transaction
def insert_note(cur: sqlite3.Cursor, chat_id: int | None, note: str):
    @newest_chat_id
    def default_to_newest(chat_id: int):
        cur.execute(
            "INSERT INTO notes (chat_id, note, created_at) VALUES (?, ?, datetime('now'))",
            (chat_id, note),
        )

    default_to_newest(chat_id)


# in general, I am preferring to defer JSON deserialization
# because otherwise we have cases where we deserialize than immediately serialize
# when we pass to the LLM
@newest_chat_id
@transaction
def get_chat(cur: sqlite3.Cursor, chat_id: int) -> str:
    cur.execute(
        "SELECT json(messages) AS history FROM chat_history WHERE chat_id = ?",
        (chat_id,),
    )
    result = cur.fetchone()
    try:
        result = result["history"]
    except TypeError:
        raise ValueError("Chat ID not found") from None
    return result


@transaction
def get_user_chats(cur: sqlite3.Cursor, chat_id: int) -> list[str]:
    cur.execute(
        "SELECT m.value->>'content' AS content FROM chat_history c, json_each(c.messages) m"
        " WHERE c.chat_id = ? AND m.value->>'role' = 'user' AND m.key != 0"
        " ORDER BY m.key",
        (chat_id,),
    )

    def get_rows():
        while (row := cur.fetchone()) is not None:
            yield row

    return [row["content"] for row in get_rows()]


@newest_chat_id
@transaction
def get_final_chat(cur, chat_id: int) -> str:
    cur.execute(
        "SELECT m.value AS message FROM chat_history c, json_each(c.messages) m"
        " WHERE c.chat_id = ? ORDER BY m.key DESC LIMIT 1",
        (chat_id,),
    )
    result = cur.fetchone()
    try:
        result = result["message"]
    except TypeError:
        raise ValueError("Chat ID not found") from None
    return result


class ChatNote(TypedDict):
    chat_id: int
    note: str


@transaction
def get_random_chat_notes(cur, n: int) -> list[ChatNote]:
    cur.execute(
        "SELECT chat_id, note FROM notes ORDER BY random() LIMIT ?",
        (n,),
    )
    return cur.fetchall()
