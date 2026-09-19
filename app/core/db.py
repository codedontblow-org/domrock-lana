import sqlite3
from contextlib import contextmanager
from app.core.config import get_settings

@contextmanager
def get_connection():
    settings = get_settings()
    conn = sqlite3.connect(settings.DATABASE_SQLITE_URL)
    conn.row_factory = sqlite3.Row 
    try:
        yield conn
    finally:
        conn.close()

def executar_select(sql: str) -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        return [dict(row) for row in cursor.fetchall()]