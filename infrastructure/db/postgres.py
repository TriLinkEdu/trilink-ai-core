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
    # Add keepalive and SSL settings to prevent connection drops
    _pool = pool.ThreadedConnectionPool(
        minconn, 
        maxconn, 
        dsn,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
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
        # Retry logic for transient connection errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._conn = get_pool().getconn()
                # Test connection is alive with a fast ping
                with self._conn.cursor() as cur:
                    cur.execute("SELECT 1")
                self._conn.rollback()
                return self._conn
            except psycopg2.Error as e:
                if self._conn:
                    try:
                        get_pool().putconn(self._conn, close=True)
                    except:
                        pass
                if attempt == max_retries - 1:
                    raise
                # Retry on next iteration
                continue
        return self._conn

    def __exit__(self, exc_type, *_):
        if self._conn:
            try:
                if exc_type:
                    self._conn.rollback()
                else:
                    self._conn.commit()
            except psycopg2.Error:
                # Connection already closed, just discard it
                try:
                    get_pool().putconn(self._conn, close=True)
                except:
                    pass
                return
            get_pool().putconn(self._conn)


def connection() -> _Conn:
    """Usage:  with connection() as conn: ..."""
    return _Conn()
