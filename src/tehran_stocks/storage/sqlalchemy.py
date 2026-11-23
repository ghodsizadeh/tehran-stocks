"""SQLAlchemy 2.0 Core storage backend supporting SQLite, PostgreSQL, DuckDB, and MySQL."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
import importlib.util
from pathlib import Path
from typing import Any, NoReturn

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    case,
    create_engine,
    delete,
    event,
    func,
    or_,
    select,
    text,
    tuple_,
)
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import NoSuchModuleError, SQLAlchemyError
from sqlalchemy.pool import StaticPool

from tehran_stocks.exceptions import StorageError
from tehran_stocks.storage._sql import (
    SCHEMA_VERSION,
    TABLE_NAMES,
    adjustment_to_row,
    client_type_to_row,
    coerce_row_date,
    coerce_storage_date,
    daily_bar_to_row,
    dedupe_rows,
    escape_like,
    instrument_to_row,
    normalize_identifier,
    normalize_persian,
    normalize_sector_code,
    resolve_for_query,
    row_to_adjustment,
    row_to_client_type,
    row_to_daily_bar,
    row_to_instrument,
    sector_to_row,
    share_change_to_row,
    slice_recent,
    utc_now_iso,
    validate_limit,
    validate_readonly_sql,
)
from tehran_stocks.types.client_type import ClientTypeDaily
from tehran_stocks.types.instrument import Instrument, ShareChange
from tehran_stocks.types.market import Sector
from tehran_stocks.types.price import DailyBar, PriceAdjustment
from tehran_stocks.utils.analytics import adjust_prices

_UPSERT_CHUNK_SIZE = 50

metadata = MetaData()

sectors_table = Table(
    "sectors",
    metadata,
    Column("code", String(16), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("type", String(64), nullable=False, server_default=""),
    Column("index_ins_code", String(32), nullable=False, server_default=""),
    Column("trade_value", BigInteger, nullable=False, server_default="0"),
    Column("trade_volume", BigInteger, nullable=False, server_default="0"),
    Column("trade_count", BigInteger, nullable=False, server_default="0"),
    Column("market_cap", Float(precision=53), nullable=False, server_default="0"),
)

instruments_table = Table(
    "instruments",
    metadata,
    Column("ins_code", String(32), primary_key=True),
    Column("symbol", String(128), nullable=False),
    Column("name", String(255), nullable=False),
    Column("isin", String(32), nullable=False, server_default=""),
    Column("instrument_id", String(32), nullable=False, server_default=""),
    Column("market", String(128), nullable=False, server_default=""),
    Column("flow", Integer, nullable=True),
    Column("sector_code", String(16), nullable=False, server_default=""),
    Column("sector_name", String(255), nullable=False, server_default=""),
    Column("total_shares", BigInteger, nullable=False, server_default="0"),
    Index("ix_instruments_symbol", "symbol"),
    Index("ix_instruments_isin", "isin"),
    Index("ix_instruments_sector_code", "sector_code"),
)

daily_prices_table = Table(
    "daily_prices",
    metadata,
    Column("ins_code", String(32), primary_key=True),
    Column("date", Date, primary_key=True),
    Column("open", Float(precision=53), nullable=False),
    Column("high", Float(precision=53), nullable=False),
    Column("low", Float(precision=53), nullable=False),
    Column("close", Float(precision=53), nullable=False),
    Column("last", Float(precision=53), nullable=False),
    Column("yesterday", Float(precision=53), nullable=False, server_default="0"),
    Column("volume", BigInteger, nullable=False, server_default="0"),
    Column("value", BigInteger, nullable=False, server_default="0"),
    Column("trade_count", BigInteger, nullable=False, server_default="0"),
    Index("ix_daily_prices_date", "date"),
)

client_types_table = Table(
    "client_types",
    metadata,
    Column("ins_code", String(32), primary_key=True),
    Column("date", Date, primary_key=True),
    Column("buy_i_volume", BigInteger, nullable=False, server_default="0"),
    Column("buy_n_volume", BigInteger, nullable=False, server_default="0"),
    Column("sell_i_volume", BigInteger, nullable=False, server_default="0"),
    Column("sell_n_volume", BigInteger, nullable=False, server_default="0"),
    Column("buy_i_count", BigInteger, nullable=False, server_default="0"),
    Column("buy_n_count", BigInteger, nullable=False, server_default="0"),
    Column("sell_i_count", BigInteger, nullable=False, server_default="0"),
    Column("sell_n_count", BigInteger, nullable=False, server_default="0"),
    Column("buy_i_value", BigInteger, nullable=False, server_default="0"),
    Column("buy_n_value", BigInteger, nullable=False, server_default="0"),
    Column("sell_i_value", BigInteger, nullable=False, server_default="0"),
    Column("sell_n_value", BigInteger, nullable=False, server_default="0"),
    Index("ix_client_types_date", "date"),
)

price_adjustments_table = Table(
    "price_adjustments",
    metadata,
    Column("ins_code", String(32), primary_key=True),
    Column("date", Date, primary_key=True),
    Column("event_key", String(64), primary_key=True),
    Column("adjusted_close", Float(precision=53), nullable=False),
    Column("unadjusted_close", Float(precision=53), nullable=False),
    Column("corporate_type_code", String(32), nullable=True),
)

share_changes_table = Table(
    "share_changes",
    metadata,
    Column("ins_code", String(32), primary_key=True),
    Column("date", Date, primary_key=True),
    Column("new_shares", BigInteger, nullable=False),
    Column("old_shares", BigInteger, nullable=False),
)

sync_meta_table = Table(
    "sync_meta",
    metadata,
    Column("key", String(128), primary_key=True),
    Column("value", Text, nullable=False),
    Column("updated_at", String(64), nullable=False),
)

_TABLES_BY_NAME: dict[str, Table] = {
    "sectors": sectors_table,
    "instruments": instruments_table,
    "daily_prices": daily_prices_table,
    "client_types": client_types_table,
    "price_adjustments": price_adjustments_table,
    "share_changes": share_changes_table,
    "sync_meta": sync_meta_table,
}


def normalize_sqlalchemy_url(target: str | Path) -> str:
    """Normalize paths, ``:memory:``, and shorthand DB URLs for SQLAlchemy 2.0."""
    if isinstance(target, Path):
        target.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{target}"

    raw = str(target).strip()
    if raw in (":memory:", "sqlite://", "sqlite:///:memory:"):
        return "sqlite:///:memory:"
    if "://" not in raw:
        path = Path(raw)
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"

    lower = raw.lower()
    if lower.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
        lower = raw.lower()

    if lower.startswith("postgresql://"):
        if (
            importlib.util.find_spec("psycopg2") is None
            and importlib.util.find_spec("psycopg") is not None
        ):
            raw = "postgresql+psycopg://" + raw[len("postgresql://") :]

    return raw


def _raise_driver_or_db_error(exc: Exception, url: str) -> NoReturn:
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""
    if isinstance(exc, (ModuleNotFoundError, ImportError, NoSuchModuleError)) or (
        "No module named" in str(exc)
    ):
        if "postgres" in scheme:
            raise StorageError(
                f"PostgreSQL driver is not installed ({exc}). "
                "Install it with: pip install 'tehran-stocks[postgres]'"
            ) from exc
        if "duckdb" in scheme:
            raise StorageError(
                f"DuckDB driver is not installed ({exc}). "
                "Install it with: pip install 'tehran-stocks[duckdb]'"
            ) from exc
        raise StorageError(
            f"Database driver for {scheme or url!r} is not installed ({exc})."
        ) from exc
    raise StorageError(f"SQLAlchemy storage error: {exc}") from exc


def _flow_priority_expr() -> Any:
    return case(
        (instruments_table.c.flow == 1, 4),
        (instruments_table.c.flow == 2, 3),
        (instruments_table.c.flow == 4, 2),
        else_=1,
    )


class SQLAlchemyStore:
    """SQLAlchemy 2.0 Core storage backend for SQLite, PostgreSQL, DuckDB, and MySQL."""

    def __init__(
        self,
        url: str | Path,
        *,
        auto_init: bool = True,
        echo: bool = False,
        **engine_kwargs: Any,
    ) -> None:
        self.url = normalize_sqlalchemy_url(url)
        self._closed = False
        is_sqlite_memory = self.url == "sqlite:///:memory:"

        kwargs = dict(engine_kwargs)
        kwargs.setdefault("future", True)
        kwargs.setdefault("echo", echo)
        if self.url.lower().startswith("sqlite"):
            connect_args = dict(kwargs.get("connect_args") or {})
            connect_args.setdefault("check_same_thread", False)
            kwargs["connect_args"] = connect_args
            if is_sqlite_memory:
                kwargs.setdefault("poolclass", StaticPool)

        try:
            self._engine: Engine = create_engine(self.url, **kwargs)
        except Exception as exc:
            _raise_driver_or_db_error(exc, self.url)

        self.dialect_name = self._engine.dialect.name

        if self.dialect_name == "sqlite":
            @event.listens_for(self._engine, "connect")
            def _configure_sqlite(dbapi_conn: Any, _connection_record: Any) -> None:
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys = ON")
                if not is_sqlite_memory:
                    cursor.execute("PRAGMA journal_mode = WAL")
                    cursor.execute("PRAGMA synchronous = NORMAL")
                cursor.close()

        if auto_init:
            self.init_schema()

    def _ensure_open(self) -> None:
        if self._closed:
            raise StorageError("SQLAlchemyStore engine is closed")

    def init_schema(self) -> None:
        """Create tables and indexes idempotently using SQLAlchemy Core metadata."""
        self._ensure_open()
        try:
            with self._engine.begin() as conn:
                if self.dialect_name == "sqlite":
                    version = int(conn.exec_driver_sql("PRAGMA user_version").scalar_one())
                    if version > SCHEMA_VERSION:
                        raise StorageError(
                            f"Database schema version {version} is newer than supported "
                            f"version {SCHEMA_VERSION}"
                        )
                metadata.create_all(conn, checkfirst=True)
                existing_meta = conn.execute(
                    select(sync_meta_table.c.value).where(
                        sync_meta_table.c.key == "schema_version"
                    )
                ).scalar_one_or_none()
                if existing_meta is not None and str(existing_meta).strip().isdigit():
                    if int(str(existing_meta).strip()) > SCHEMA_VERSION:
                        raise StorageError(
                            f"Database schema version {existing_meta} is newer than supported "
                            f"version {SCHEMA_VERSION}"
                        )
                if self.dialect_name == "sqlite":
                    version = int(conn.exec_driver_sql("PRAGMA user_version").scalar_one())
                    if version < SCHEMA_VERSION:
                        conn.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")
                self._upsert_chunk(
                    conn,
                    sync_meta_table,
                    ("key",),
                    [
                        {
                            "key": "schema_version",
                            "value": str(SCHEMA_VERSION),
                            "updated_at": utc_now_iso(),
                        }
                    ],
                )
        except StorageError:
            raise
        except Exception as exc:
            _raise_driver_or_db_error(exc, self.url)

    def close(self) -> None:
        """Dispose the underlying SQLAlchemy engine and connection pool."""
        if not self._closed:
            self._engine.dispose()
            self._closed = True

    def __enter__(self) -> SQLAlchemyStore:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _upsert_chunk(
        self,
        conn: Connection,
        table: Table,
        pk_cols: tuple[str, ...],
        chunk: list[dict[str, Any]],
    ) -> None:
        update_cols = [col.name for col in table.columns if col.name not in pk_cols]

        if self.dialect_name in ("sqlite", "postgresql"):
            insert_fn = sqlite_insert if self.dialect_name == "sqlite" else pg_insert
            stmt = insert_fn(table).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=list(pk_cols),
                set_={col: stmt.excluded[col] for col in update_cols},
            )
            conn.execute(stmt)
            return

        if self.dialect_name in ("mysql", "mariadb"):
            stmt = mysql_insert(table).values(chunk)
            stmt = stmt.on_duplicate_key_update(
                **{col: stmt.inserted[col] for col in update_cols}
            )
            conn.execute(stmt)
            return

        if len(pk_cols) == 1:
            pk_name = pk_cols[0]
            keys = [row[pk_name] for row in chunk]
            conn.execute(delete(table).where(table.c[pk_name].in_(keys)))
        else:
            key_tuples = [tuple(row[k] for k in pk_cols) for row in chunk]
            conn.execute(
                delete(table).where(tuple_(*(table.c[k] for k in pk_cols)).in_(key_tuples))
            )
        conn.execute(table.insert(), chunk)

    def _batch_upsert(
        self,
        table: Table,
        pk_cols: tuple[str, ...],
        rows: list[dict[str, Any]],
    ) -> int:
        if not rows:
            return 0
        self._ensure_open()
        try:
            with self._engine.begin() as conn:
                for start in range(0, len(rows), _UPSERT_CHUNK_SIZE):
                    self._upsert_chunk(
                        conn,
                        table,
                        pk_cols,
                        rows[start : start + _UPSERT_CHUNK_SIZE],
                    )
        except Exception as exc:
            _raise_driver_or_db_error(exc, self.url)
        return len(rows)

    def upsert_sectors(self, sectors: Sequence[Sector]) -> int:
        rows = dedupe_rows((sector_to_row(s) for s in sectors if str(s.code).strip()), ("code",))
        return self._batch_upsert(sectors_table, ("code",), rows)

    def upsert_instruments(self, instruments: Sequence[Instrument]) -> int:
        rows = dedupe_rows(
            (instrument_to_row(inst) for inst in instruments if str(inst.ins_code).strip()),
            ("ins_code",),
        )
        return self._batch_upsert(instruments_table, ("ins_code",), rows)

    def upsert_prices(self, bars: Sequence[DailyBar]) -> int:
        rows = dedupe_rows(
            (daily_bar_to_row(bar, date_as_str=False) for bar in bars if str(bar.ins_code).strip()),
            ("ins_code", "date"),
        )
        return self._batch_upsert(daily_prices_table, ("ins_code", "date"), rows)

    def upsert_client_types(self, records: Sequence[ClientTypeDaily]) -> int:
        rows = dedupe_rows(
            (
                client_type_to_row(rec, date_as_str=False)
                for rec in records
                if str(rec.ins_code).strip()
            ),
            ("ins_code", "date"),
        )
        return self._batch_upsert(client_types_table, ("ins_code", "date"), rows)

    def upsert_adjustments(self, adjustments: Sequence[PriceAdjustment]) -> int:
        rows = dedupe_rows(
            (
                adjustment_to_row(adj, date_as_str=False)
                for adj in adjustments
                if str(adj.ins_code).strip()
            ),
            ("ins_code", "date", "event_key"),
        )
        return self._batch_upsert(price_adjustments_table, ("ins_code", "date", "event_key"), rows)

    def upsert_share_changes(self, changes: Sequence[ShareChange]) -> int:
        rows = dedupe_rows(
            (
                share_change_to_row(sc, date_as_str=False)
                for sc in changes
                if str(sc.ins_code).strip()
            ),
            ("ins_code", "date"),
        )
        return self._batch_upsert(share_changes_table, ("ins_code", "date"), rows)

    def set_sync_meta(self, key: str, value: str) -> None:
        """Persist a key/value entry in ``sync_meta``."""
        self._batch_upsert(
            sync_meta_table,
            ("key",),
            [{"key": key, "value": value, "updated_at": utc_now_iso()}],
        )

    def get_sync_meta(self, key: str) -> str | None:
        """Read a value from ``sync_meta``."""
        self._ensure_open()
        try:
            with self._engine.connect() as conn:
                val = conn.execute(
                    select(sync_meta_table.c.value).where(sync_meta_table.c.key == key)
                ).scalar_one_or_none()
            return str(val) if val is not None else None
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to read sync_meta: {exc}") from exc

    def list_instruments(
        self,
        *,
        sector_code: str | None = None,
        query: str | None = None,
        flow: int | None = None,
        limit: int | None = None,
    ) -> list[Instrument]:
        validate_limit(limit)
        if limit == 0:
            return []

        self._ensure_open()
        stmt = select(instruments_table)
        if sector_code is not None:
            stmt = stmt.where(instruments_table.c.sector_code == normalize_sector_code(sector_code))
        if flow is not None:
            stmt = stmt.where(instruments_table.c.flow == int(flow))
        if query is not None:
            norm_query = normalize_persian(query).strip()
            if norm_query:
                escaped = f"%{escape_like(norm_query)}%"
                stmt = stmt.where(
                    or_(
                        instruments_table.c.symbol.ilike(escaped, escape="!"),
                        instruments_table.c.name.ilike(escaped, escape="!"),
                        instruments_table.c.isin.ilike(escaped, escape="!"),
                        instruments_table.c.instrument_id.ilike(escaped, escape="!"),
                        instruments_table.c.ins_code.ilike(escaped, escape="!"),
                    )
                )

        stmt = stmt.order_by(instruments_table.c.symbol.asc(), instruments_table.c.ins_code.asc())
        if limit is not None:
            stmt = stmt.limit(int(limit))

        try:
            with self._engine.connect() as conn:
                rows = conn.execute(stmt).mappings().all()
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to list instruments: {exc}") from exc
        return [row_to_instrument(row) for row in rows]

    def resolve_ins_code(self, identifier: str | int) -> str | None:
        normalized = normalize_identifier(identifier)
        if not normalized or normalized == "0":
            return None
        upper = normalized.upper()

        self._ensure_open()
        try:
            with self._engine.connect() as conn:
                direct = conn.execute(
                    select(instruments_table.c.ins_code)
                    .where(instruments_table.c.ins_code == normalized)
                    .limit(1)
                ).scalar_one_or_none()
                if direct is not None:
                    return str(direct)

                by_symbol = conn.execute(
                    select(instruments_table.c.ins_code)
                    .where(instruments_table.c.symbol == normalized)
                    .order_by(
                        _flow_priority_expr().desc(),
                        instruments_table.c.total_shares.desc(),
                        instruments_table.c.ins_code.asc(),
                    )
                    .limit(1)
                ).scalar_one_or_none()
                if by_symbol is not None:
                    return str(by_symbol)

                by_isin = conn.execute(
                    select(instruments_table.c.ins_code)
                    .where(
                        or_(
                            func.upper(instruments_table.c.isin) == upper,
                            func.upper(instruments_table.c.instrument_id) == upper,
                        )
                    )
                    .order_by(
                        _flow_priority_expr().desc(),
                        instruments_table.c.total_shares.desc(),
                        instruments_table.c.ins_code.asc(),
                    )
                    .limit(1)
                ).scalar_one_or_none()
                if by_isin is not None:
                    return str(by_isin)
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to resolve instrument {identifier!r}: {exc}") from exc
        return None

    def _get_max_date(self, table: Table, symbol: str | int) -> date | None:
        ins_code = resolve_for_query(self.resolve_ins_code, symbol)
        if ins_code is None:
            return None
        self._ensure_open()
        try:
            with self._engine.connect() as conn:
                val = conn.execute(
                    select(func.max(table.c.date)).where(table.c.ins_code == ins_code)
                ).scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to read max date from {table.name}: {exc}") from exc
        return coerce_row_date(val) if val is not None else None

    def get_last_price_date(self, symbol: str | int) -> date | None:
        return self._get_max_date(daily_prices_table, symbol)

    def get_last_client_type_date(self, symbol: str | int) -> date | None:
        return self._get_max_date(client_types_table, symbol)

    def get_adjustments(self, symbol: str | int) -> list[PriceAdjustment]:
        ins_code = resolve_for_query(self.resolve_ins_code, symbol)
        if ins_code is None:
            return []
        self._ensure_open()
        try:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    select(price_adjustments_table)
                    .where(price_adjustments_table.c.ins_code == ins_code)
                    .order_by(
                        price_adjustments_table.c.date.asc(),
                        price_adjustments_table.c.event_key.asc(),
                    )
                ).mappings().all()
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to read price adjustments: {exc}") from exc
        return [row_to_adjustment(row) for row in rows]

    def _query_date_series(
        self,
        table: Table,
        symbol: str | int,
        *,
        start: date | int | str | None,
        end: date | int | str | None,
    ) -> tuple[str | None, list[Any]]:
        ins_code = resolve_for_query(self.resolve_ins_code, symbol)
        if ins_code is None:
            return None, []

        start_date = coerce_storage_date(start)
        end_date = coerce_storage_date(end)

        self._ensure_open()
        stmt = select(table).where(table.c.ins_code == ins_code)
        if start_date is not None:
            stmt = stmt.where(table.c.date >= start_date)
        if end_date is not None:
            stmt = stmt.where(table.c.date <= end_date)
        stmt = stmt.order_by(table.c.date.asc())

        try:
            with self._engine.connect() as conn:
                rows = conn.execute(stmt).mappings().all()
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to query {table.name}: {exc}") from exc
        return ins_code, rows

    def get_prices(
        self,
        symbol: str | int,
        *,
        start: date | int | str | None = None,
        end: date | int | str | None = None,
        adjusted: bool = False,
        limit: int | None = None,
    ) -> list[DailyBar]:
        validate_limit(limit)
        if limit == 0:
            return []

        ins_code, rows = self._query_date_series(daily_prices_table, symbol, start=start, end=end)
        if ins_code is None:
            return []

        bars = [row_to_daily_bar(row) for row in rows]
        if adjusted and bars:
            bars = adjust_prices(bars, self.get_adjustments(ins_code))
        return slice_recent(bars, limit)

    def get_client_types(
        self,
        symbol: str | int,
        *,
        start: date | int | str | None = None,
        end: date | int | str | None = None,
        limit: int | None = None,
    ) -> list[ClientTypeDaily]:
        validate_limit(limit)
        if limit == 0:
            return []

        ins_code, rows = self._query_date_series(client_types_table, symbol, start=start, end=end)
        if ins_code is None:
            return []

        return slice_recent([row_to_client_type(row) for row in rows], limit)

    def query_readonly(
        self,
        sql: str,
        params: Mapping[str, Any] | Sequence[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a validated ``SELECT``/``WITH`` query inside a rolled-back transaction."""
        cleaned_sql = validate_readonly_sql(sql, allow_pragma=False)
        self._ensure_open()

        try:
            with self._engine.connect() as conn:
                trans = conn.begin()
                try:
                    if self.dialect_name == "sqlite":
                        conn.exec_driver_sql("PRAGMA query_only = ON")
                    elif self.dialect_name == "postgresql":
                        conn.exec_driver_sql("SET TRANSACTION READ ONLY")

                    if params is None:
                        result = conn.execute(text(cleaned_sql))
                    elif isinstance(params, Mapping):
                        result = conn.execute(text(cleaned_sql), dict(params))
                    else:
                        result = conn.exec_driver_sql(cleaned_sql, tuple(params))

                    if not result.returns_rows:
                        return []
                    return [dict(row) for row in result.mappings().all()]
                finally:
                    if self.dialect_name == "sqlite":
                        try:
                            conn.exec_driver_sql("PRAGMA query_only = OFF")
                        except SQLAlchemyError:
                            pass
                    trans.rollback()
        except SQLAlchemyError as exc:
            raise StorageError(f"Read-only query failed: {exc}") from exc

    def stats(self) -> dict[str, Any]:
        self._ensure_open()
        try:
            with self._engine.connect() as conn:
                summary: dict[str, Any] = {
                    "backend": "sqlalchemy",
                    "dialect": self.dialect_name,
                    "schema_version": SCHEMA_VERSION,
                }
                for name in TABLE_NAMES:
                    table = _TABLES_BY_NAME[name]
                    summary[name] = int(
                        conn.execute(select(func.count()).select_from(table)).scalar_one()
                    )

                min_p, max_p = conn.execute(
                    select(
                        func.min(daily_prices_table.c.date),
                        func.max(daily_prices_table.c.date),
                    )
                ).one()
                min_ct, max_ct = conn.execute(
                    select(
                        func.min(client_types_table.c.date),
                        func.max(client_types_table.c.date),
                    )
                ).one()

                summary["min_price_date"] = (
                    coerce_row_date(min_p).isoformat() if min_p is not None else None
                )
                summary["max_price_date"] = (
                    coerce_row_date(max_p).isoformat() if max_p is not None else None
                )
                summary["min_client_type_date"] = (
                    coerce_row_date(min_ct).isoformat() if min_ct is not None else None
                )
                summary["max_client_type_date"] = (
                    coerce_row_date(max_ct).isoformat() if max_ct is not None else None
                )
                summary["last_sectors_sync"] = self.get_sync_meta("last_sectors_sync")
                summary["last_instruments_sync"] = self.get_sync_meta("last_instruments_sync")
                return summary
        except SQLAlchemyError as exc:
            raise StorageError(f"Failed to compute SQLAlchemy storage stats: {exc}") from exc
