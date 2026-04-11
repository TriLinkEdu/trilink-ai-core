"""
MongoDB client — used for chat logs and audit trails.
Uses certifi for TLS compatibility with Python 3.13 + OpenSSL 3.5.
"""
import certifi
from pymongo import MongoClient
from pymongo.database import Database

_client: MongoClient | None = None
_db: Database | None = None


def init_mongo(url: str, db_name: str = "trilink") -> None:
    global _client, _db
    _client = MongoClient(url, tlsCAFile=certifi.where())
    _db = _client[db_name]


def get_db() -> Database:
    if _db is None:
        raise RuntimeError("MongoDB not initialised — call init_mongo() first")
    return _db
