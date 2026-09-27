import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from app.core.config import get_settings


@contextmanager
def get_connection():
    settings = get_settings()
    conn = psycopg2.connect(settings.DATABASE_URL)
    # Defesa em profundidade além do papel lana_leitura: sessão só de leitura e com timeout.
    conn.set_session(readonly=True, autocommit=True)
    with conn.cursor() as cursor:
        cursor.execute("SET statement_timeout = '15s'")
    try:
        yield conn
    finally:
        conn.close()


def executar_select(sql: str) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]