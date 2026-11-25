"""Opt-in persistence layer, store factory, and incremental sync services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tehran_stocks.exceptions import StorageError
from tehran_stocks.storage.protocol import StorageBackend
from tehran_stocks.storage.sqlalchemy import SQLAlchemyStore
from tehran_stocks.storage.sqlite import SQLiteStore
from tehran_stocks.storage.sync import AsyncSyncService, SyncProgress, SyncResult, SyncService


def _is_plain_sqlite_url(target: str) -> bool:
    lower = target.lower()
    if lower in (":memory:", "sqlite://", "sqlite:///:memory:"):
        return True
    return lower.startswith("sqlite:///")


def open_store(
    target: str | Path = ":memory:",
    *,
    backend: str | None = None,
    init_schema: bool = True,
    read_only: bool = False,
    **kwargs: Any,
) -> SQLiteStore | SQLAlchemyStore:
    """Open a ``SQLiteStore`` for local paths/``sqlite://`` or ``SQLAlchemyStore`` for DB URLs.

    Examples:
        ``open_store("market.db")`` -> ``SQLiteStore``
        ``open_store(":memory:")`` -> ``SQLiteStore``
        ``open_store("postgresql://user:pass@localhost/tse")`` -> ``SQLAlchemyStore``
        ``open_store("duckdb:///tse.duckdb")`` -> ``SQLAlchemyStore``
        ``open_store("market.db", backend="sqlalchemy")`` -> ``SQLAlchemyStore``

    ``read_only=True`` opens a local SQLite file with ``?mode=ro`` and leaves its journal mode
    alone (see ``SQLiteStore``). It applies to ``SQLiteStore`` only.
    """
    chosen = backend.strip().lower() if backend is not None else None

    if chosen is not None and chosen not in ("sqlite", "sqlalchemy"):
        raise StorageError(
            f"Unsupported storage backend {backend!r}; expected 'sqlite' or 'sqlalchemy'"
        )

    if chosen == "sqlalchemy":
        return SQLAlchemyStore(target, auto_init=init_schema, **kwargs)

    if chosen == "sqlite":
        return SQLiteStore(target, auto_init=init_schema, read_only=read_only, **kwargs)

    if isinstance(target, Path):
        return SQLiteStore(target, auto_init=init_schema, read_only=read_only, **kwargs)

    raw = str(target).strip()
    if not raw:
        raise StorageError("Storage target cannot be empty")

    if "://" not in raw or _is_plain_sqlite_url(raw):
        return SQLiteStore(raw, auto_init=init_schema, read_only=read_only, **kwargs)

    return SQLAlchemyStore(raw, auto_init=init_schema, **kwargs)


__all__ = [
    "AsyncSyncService",
    "SQLAlchemyStore",
    "SQLiteStore",
    "StorageBackend",
    "SyncProgress",
    "SyncResult",
    "SyncService",
    "open_store",
]
