"""
PostgreSQL connection pool.
All repositories share one pool — created once at startup.
"""
import psycopg2
from psycopg2 import pool
from pgvector.psycopg2 import register_vector

_pool: pool.ThreadedConnectionPool | None = None


def init_pool(dsn: str, minconn: int = 2, maxconn: int = 10) -> None:
    global _pool
    _pool = pool.ThreadedConnectionPool(minconn, maxconn, dsn)
    # Register pgvector type on a throwaway connection
    conn = _pool.getconn()
    try:
        register_vector(conn)
    finally:
        _pool.putconn(conn)


def get_pool() -> pool.ThreadedConnectionPool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() first")
    return _pool


class _Conn:
    """Context manager: borrows a connection, auto-commits or rolls back."""

    def __init__(self):
        self._conn = None

    def __enter__(self):
        self._conn = get_pool().getconn()
        return self._conn

    def __exit__(self, exc_type, *_):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        get_pool().putconn(self._conn)


def connection() -> _Conn:
    """Usage:  with connection() as conn: ..."""
    return _Conn()
