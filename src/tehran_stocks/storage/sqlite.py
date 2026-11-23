"""Zero-dependency SQLite storage backend using Python's stdlib ``sqlite3``."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
import sqlite3
import threading
from typing import Any

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

_DDL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS sectors (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT '',
        index_ins_code TEXT NOT NULL DEFAULT '',
        trade_value INTEGER NOT NULL DEFAULT 0,
        trade_volume INTEGER NOT NULL DEFAULT 0,
        trade_count INTEGER NOT NULL DEFAULT 0,
        market_cap REAL NOT NULL DEFAULT 0.0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS instruments (
        ins_code TEXT PRIMARY KEY,
        symbol TEXT NOT NULL,
        name TEXT NOT NULL,
        isin TEXT NOT NULL DEFAULT '',
        instrument_id TEXT NOT NULL DEFAULT '',
        market TEXT NOT NULL DEFAULT '',
        flow INTEGER NULL,
        sector_code TEXT NOT NULL DEFAULT '',
        sector_name TEXT NOT NULL DEFAULT '',
        total_shares INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_instruments_symbol ON instruments (symbol)",
    "CREATE INDEX IF NOT EXISTS ix_instruments_isin ON instruments (isin)",
    "CREATE INDEX IF NOT EXISTS ix_instruments_sector_code ON instruments (sector_code)",
    """
    CREATE TABLE IF NOT EXISTS daily_prices (
        ins_code TEXT NOT NULL,
        date DATE NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        last REAL NOT NULL,
        yesterday REAL NOT NULL DEFAULT 0.0,
        volume INTEGER NOT NULL DEFAULT 0,
        value INTEGER NOT NULL DEFAULT 0,
        trade_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (ins_code, date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_daily_prices_date ON daily_prices (date)",
    """
    CREATE TABLE IF NOT EXISTS client_types (
        ins_code TEXT NOT NULL,
        date DATE NOT NULL,
        buy_i_volume INTEGER NOT NULL DEFAULT 0,
        buy_n_volume INTEGER NOT NULL DEFAULT 0,
        sell_i_volume INTEGER NOT NULL DEFAULT 0,
        sell_n_volume INTEGER NOT NULL DEFAULT 0,
        buy_i_count INTEGER NOT NULL DEFAULT 0,
        buy_n_count INTEGER NOT NULL DEFAULT 0,
        sell_i_count INTEGER NOT NULL DEFAULT 0,
        sell_n_count INTEGER NOT NULL DEFAULT 0,
        buy_i_value INTEGER NOT NULL DEFAULT 0,
        buy_n_value INTEGER NOT NULL DEFAULT 0,
        sell_i_value INTEGER NOT NULL DEFAULT 0,
        sell_n_value INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (ins_code, date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_client_types_date ON client_types (date)",
    """
    CREATE TABLE IF NOT EXISTS price_adjustments (
        ins_code TEXT NOT NULL,
        date DATE NOT NULL,
        event_key TEXT NOT NULL,
        adjusted_close REAL NOT NULL,
        unadjusted_close REAL NOT NULL,
        corporate_type_code TEXT NULL,
        PRIMARY KEY (ins_code, date, event_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS share_changes (
        ins_code TEXT NOT NULL,
        date DATE NOT NULL,
        new_shares INTEGER NOT NULL,
        old_shares INTEGER NOT NULL,
        PRIMARY KEY (ins_code, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sync_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
)


def _parse_sqlite_target(target: str | Path) -> Path | None:
    if isinstance(target, Path):
        return target
    raw = str(target).strip()
    if raw in (":memory:", "sqlite://", "sqlite:///:memory:"):
        return None
    if raw.lower().startswith("sqlite:///"):
        rest = raw[len("sqlite:///") :].split("#", 1)[0].split("?", 1)[0]
        if not rest or rest == ":memory:":
            return None
        return Path(rest)
    if "://" in raw:
        raise StorageError(f"Unsupported database URI for SQLiteStore: {target!r}")
    return Path(raw)


class SQLiteStore:
    """Built-in SQLite storage backend with WAL mode, migrations, and read-only queries."""

    def __init__(
        self,
        target: str | Path = ":memory:",
        *,
        auto_init: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self.path = _parse_sqlite_target(target)
        self._is_memory = self.path is None
        self._timeout = float(timeout)
        self._lock = threading.RLock()
        self._closed = False

        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db_arg = str(self.path)
        else:
            db_arg = ":memory:"

        try:
            self._conn = sqlite3.connect(
                db_arg,
                timeout=self._timeout,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute(f"PRAGMA busy_timeout = {max(int(self._timeout * 1000), 1000)}")
            if not self._is_memory:
                self._conn.execute("PRAGMA journal_mode = WAL")
                self._conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to open SQLite database {target!r}: {exc}") from exc

        if auto_init:
            self.init_schema()

    def _ensure_open(self) -> None:
        if self._closed:
            raise StorageError("SQLiteStore connection is closed")

    def init_schema(self) -> None:
        """Create tables and indexes idempotently and apply ``PRAGMA user_version``."""
        with self._lock:
            self._ensure_open()
            try:
                current_version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
                if current_version > SCHEMA_VERSION:
                    raise StorageError(
                        f"Database schema version {current_version} is newer than supported "
                        f"version {SCHEMA_VERSION}"
                    )
                with self._conn:
                    for ddl in _DDL_STATEMENTS:
                        self._conn.execute(ddl)
                    if current_version < SCHEMA_VERSION:
                        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                    self._conn.execute(
                        """
                        INSERT INTO sync_meta (key, value, updated_at)
                        VALUES (:key, :value, :updated_at)
                        ON CONFLICT(key) DO UPDATE SET
                            value = excluded.value,
                            updated_at = excluded.updated_at
                        """,
                        {
                            "key": "schema_version",
                            "value": str(SCHEMA_VERSION),
                            "updated_at": utc_now_iso(),
                        },
                    )
            except sqlite3.Error as exc:
                raise StorageError(f"Failed to initialize SQLite schema: {exc}") from exc

    def close(self) -> None:
        """Close the SQLite connection."""
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    def __enter__(self) -> SQLiteStore:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _executemany_upsert(self, sql: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        with self._lock:
            self._ensure_open()
            try:
                with self._conn:
                    self._conn.executemany(sql, rows)
            except sqlite3.Error as exc:
                raise StorageError(f"SQLite upsert failed: {exc}") from exc
        return len(rows)

    def upsert_sectors(self, sectors: Sequence[Sector]) -> int:
        rows = dedupe_rows((sector_to_row(s) for s in sectors if str(s.code).strip()), ("code",))
        return self._executemany_upsert(
            """
            INSERT INTO sectors (
                code, name, type, index_ins_code,
                trade_value, trade_volume, trade_count, market_cap
            ) VALUES (
                :code, :name, :type, :index_ins_code,
                :trade_value, :trade_volume, :trade_count, :market_cap
            )
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                type = excluded.type,
                index_ins_code = excluded.index_ins_code,
                trade_value = excluded.trade_value,
                trade_volume = excluded.trade_volume,
                trade_count = excluded.trade_count,
                market_cap = excluded.market_cap
            """,
            rows,
        )

    def upsert_instruments(self, instruments: Sequence[Instrument]) -> int:
        rows = dedupe_rows(
            (instrument_to_row(inst) for inst in instruments if str(inst.ins_code).strip()),
            ("ins_code",),
        )
        return self._executemany_upsert(
            """
            INSERT INTO instruments (
                ins_code, symbol, name, isin, instrument_id,
                market, flow, sector_code, sector_name, total_shares
            ) VALUES (
                :ins_code, :symbol, :name, :isin, :instrument_id,
                :market, :flow, :sector_code, :sector_name, :total_shares
            )
            ON CONFLICT(ins_code) DO UPDATE SET
                symbol = excluded.symbol,
                name = excluded.name,
                isin = excluded.isin,
                instrument_id = excluded.instrument_id,
                market = excluded.market,
                flow = excluded.flow,
                sector_code = excluded.sector_code,
                sector_name = excluded.sector_name,
                total_shares = excluded.total_shares
            """,
            rows,
        )

    def upsert_prices(self, bars: Sequence[DailyBar]) -> int:
        rows = dedupe_rows(
            (daily_bar_to_row(bar, date_as_str=True) for bar in bars if str(bar.ins_code).strip()),
            ("ins_code", "date"),
        )
        return self._executemany_upsert(
            """
            INSERT INTO daily_prices (
                ins_code, date, open, high, low, close, last,
                yesterday, volume, value, trade_count
            ) VALUES (
                :ins_code, :date, :open, :high, :low, :close, :last,
                :yesterday, :volume, :value, :trade_count
            )
            ON CONFLICT(ins_code, date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                last = excluded.last,
                yesterday = excluded.yesterday,
                volume = excluded.volume,
                value = excluded.value,
                trade_count = excluded.trade_count
            """,
            rows,
        )

    def upsert_client_types(self, records: Sequence[ClientTypeDaily]) -> int:
        rows = dedupe_rows(
            (
                client_type_to_row(rec, date_as_str=True)
                for rec in records
                if str(rec.ins_code).strip()
            ),
            ("ins_code", "date"),
        )
        return self._executemany_upsert(
            """
            INSERT INTO client_types (
                ins_code, date,
                buy_i_volume, buy_n_volume, sell_i_volume, sell_n_volume,
                buy_i_count, buy_n_count, sell_i_count, sell_n_count,
                buy_i_value, buy_n_value, sell_i_value, sell_n_value
            ) VALUES (
                :ins_code, :date,
                :buy_i_volume, :buy_n_volume, :sell_i_volume, :sell_n_volume,
                :buy_i_count, :buy_n_count, :sell_i_count, :sell_n_count,
                :buy_i_value, :buy_n_value, :sell_i_value, :sell_n_value
            )
            ON CONFLICT(ins_code, date) DO UPDATE SET
                buy_i_volume = excluded.buy_i_volume,
                buy_n_volume = excluded.buy_n_volume,
                sell_i_volume = excluded.sell_i_volume,
                sell_n_volume = excluded.sell_n_volume,
                buy_i_count = excluded.buy_i_count,
                buy_n_count = excluded.buy_n_count,
                sell_i_count = excluded.sell_i_count,
                sell_n_count = excluded.sell_n_count,
                buy_i_value = excluded.buy_i_value,
                buy_n_value = excluded.buy_n_value,
                sell_i_value = excluded.sell_i_value,
                sell_n_value = excluded.sell_n_value
            """,
            rows,
        )

    def upsert_adjustments(self, adjustments: Sequence[PriceAdjustment]) -> int:
        rows = dedupe_rows(
            (
                adjustment_to_row(adj, date_as_str=True)
                for adj in adjustments
                if str(adj.ins_code).strip()
            ),
            ("ins_code", "date", "event_key"),
        )
        return self._executemany_upsert(
            """
            INSERT INTO price_adjustments (
                ins_code, date, event_key, adjusted_close, unadjusted_close, corporate_type_code
            ) VALUES (
                :ins_code, :date, :event_key, :adjusted_close, :unadjusted_close, :corporate_type_code
            )
            ON CONFLICT(ins_code, date, event_key) DO UPDATE SET
                adjusted_close = excluded.adjusted_close,
                unadjusted_close = excluded.unadjusted_close,
                corporate_type_code = excluded.corporate_type_code
            """,
            rows,
        )

    def upsert_share_changes(self, changes: Sequence[ShareChange]) -> int:
        rows = dedupe_rows(
            (
                share_change_to_row(sc, date_as_str=True)
                for sc in changes
                if str(sc.ins_code).strip()
            ),
            ("ins_code", "date"),
        )
        return self._executemany_upsert(
            """
            INSERT INTO share_changes (ins_code, date, new_shares, old_shares)
            VALUES (:ins_code, :date, :new_shares, :old_shares)
            ON CONFLICT(ins_code, date) DO UPDATE SET
                new_shares = excluded.new_shares,
                old_shares = excluded.old_shares
            """,
            rows,
        )

    def set_sync_meta(self, key: str, value: str) -> None:
        """Persist a key/value entry in ``sync_meta``."""
        with self._lock:
            self._ensure_open()
            try:
                with self._conn:
                    self._conn.execute(
                        """
                        INSERT INTO sync_meta (key, value, updated_at)
                        VALUES (:key, :value, :updated_at)
                        ON CONFLICT(key) DO UPDATE SET
                            value = excluded.value,
                            updated_at = excluded.updated_at
                        """,
                        {"key": key, "value": value, "updated_at": utc_now_iso()},
                    )
            except sqlite3.Error as exc:
                raise StorageError(f"Failed to update sync_meta: {exc}") from exc

    def get_sync_meta(self, key: str) -> str | None:
        """Read a value from ``sync_meta``."""
        with self._lock:
            self._ensure_open()
            try:
                row = self._conn.execute(
                    "SELECT value FROM sync_meta WHERE key = ?",
                    (key,),
                ).fetchone()
                return str(row["value"]) if row is not None else None
            except sqlite3.Error as exc:
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

        clauses: list[str] = []
        params: dict[str, Any] = {}

        if sector_code is not None:
            clauses.append("sector_code = :sector_code")
            params["sector_code"] = normalize_sector_code(sector_code)

        if flow is not None:
            clauses.append("flow = :flow")
            params["flow"] = int(flow)

        if query is not None:
            norm_query = normalize_persian(query).strip()
            if norm_query:
                clauses.append(
                    "(symbol LIKE :like_pat ESCAPE '!' "
                    "OR name LIKE :like_pat ESCAPE '!' "
                    "OR LOWER(isin) LIKE :like_lower ESCAPE '!' "
                    "OR LOWER(instrument_id) LIKE :like_lower ESCAPE '!' "
                    "OR ins_code LIKE :like_pat ESCAPE '!')"
                )
                params["like_pat"] = f"%{escape_like(norm_query)}%"
                params["like_lower"] = f"%{escape_like(norm_query.lower())}%"

        sql = "SELECT * FROM instruments"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY symbol ASC, ins_code ASC"
        if limit is not None:
            sql += " LIMIT :limit"
            params["limit"] = int(limit)

        with self._lock:
            self._ensure_open()
            try:
                rows = self._conn.execute(sql, params).fetchall()
            except sqlite3.Error as exc:
                raise StorageError(f"Failed to list instruments: {exc}") from exc
        return [row_to_instrument(row) for row in rows]

    def resolve_ins_code(self, identifier: str | int) -> str | None:
        normalized = normalize_identifier(identifier)
        if not normalized or normalized == "0":
            return None
        upper = normalized.upper()

        with self._lock:
            self._ensure_open()
            try:
                row = self._conn.execute(
                    "SELECT ins_code FROM instruments WHERE ins_code = ? LIMIT 1",
                    (normalized,),
                ).fetchone()
                if row is not None:
                    return str(row["ins_code"])

                row = self._conn.execute(
                    """
                    SELECT ins_code
                    FROM instruments
                    WHERE symbol = :symbol
                    ORDER BY
                        CASE flow
                            WHEN 1 THEN 4
                            WHEN 2 THEN 3
                            WHEN 4 THEN 2
                            ELSE 1
                        END DESC,
                        total_shares DESC,
                        ins_code ASC
                    LIMIT 1
                    """,
                    {"symbol": normalized},
                ).fetchone()
                if row is not None:
                    return str(row["ins_code"])

                row = self._conn.execute(
                    """
                    SELECT ins_code
                    FROM instruments
                    WHERE UPPER(isin) = :upper OR UPPER(instrument_id) = :upper
                    ORDER BY
                        CASE flow
                            WHEN 1 THEN 4
                            WHEN 2 THEN 3
                            WHEN 4 THEN 2
                            ELSE 1
                        END DESC,
                        total_shares DESC,
                        ins_code ASC
                    LIMIT 1
                    """,
                    {"upper": upper},
                ).fetchone()
                if row is not None:
                    return str(row["ins_code"])
            except sqlite3.Error as exc:
                raise StorageError(f"Failed to resolve instrument {identifier!r}: {exc}") from exc
        return None

    def _get_max_date(self, table_name: str, symbol: str | int) -> date | None:
        ins_code = resolve_for_query(self.resolve_ins_code, symbol)
        if ins_code is None:
            return None
        with self._lock:
            self._ensure_open()
            try:
                row = self._conn.execute(
                    f"SELECT MAX(date) AS max_date FROM {table_name} WHERE ins_code = ?",
                    (ins_code,),
                ).fetchone()
            except sqlite3.Error as exc:
                raise StorageError(f"Failed to read max date from {table_name}: {exc}") from exc
        if row is None or row["max_date"] is None:
            return None
        return coerce_row_date(row["max_date"])

    def get_last_price_date(self, symbol: str | int) -> date | None:
        return self._get_max_date("daily_prices", symbol)

    def get_last_client_type_date(self, symbol: str | int) -> date | None:
        return self._get_max_date("client_types", symbol)

    def get_adjustments(self, symbol: str | int) -> list[PriceAdjustment]:
        ins_code = resolve_for_query(self.resolve_ins_code, symbol)
        if ins_code is None:
            return []
        with self._lock:
            self._ensure_open()
            try:
                rows = self._conn.execute(
                    """
                    SELECT ins_code, date, adjusted_close, unadjusted_close, corporate_type_code
                    FROM price_adjustments
                    WHERE ins_code = ?
                    ORDER BY date ASC, event_key ASC
                    """,
                    (ins_code,),
                ).fetchall()
            except sqlite3.Error as exc:
                raise StorageError(f"Failed to read price adjustments: {exc}") from exc
        return [row_to_adjustment(row) for row in rows]

    def _query_date_series(
        self,
        table_name: str,
        symbol: str | int,
        *,
        start: date | int | str | None,
        end: date | int | str | None,
    ) -> tuple[str | None, list[sqlite3.Row]]:
        ins_code = resolve_for_query(self.resolve_ins_code, symbol)
        if ins_code is None:
            return None, []

        start_date = coerce_storage_date(start)
        end_date = coerce_storage_date(end)

        clauses = ["ins_code = :ins_code"]
        params: dict[str, Any] = {"ins_code": ins_code}
        if start_date is not None:
            clauses.append("date >= :start_date")
            params["start_date"] = start_date.isoformat()
        if end_date is not None:
            clauses.append("date <= :end_date")
            params["end_date"] = end_date.isoformat()

        sql = f"SELECT * FROM {table_name} WHERE {' AND '.join(clauses)} ORDER BY date ASC"
        with self._lock:
            self._ensure_open()
            try:
                rows = self._conn.execute(sql, params).fetchall()
            except sqlite3.Error as exc:
                raise StorageError(f"Failed to query {table_name}: {exc}") from exc
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

        ins_code, rows = self._query_date_series("daily_prices", symbol, start=start, end=end)
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

        ins_code, rows = self._query_date_series("client_types", symbol, start=start, end=end)
        if ins_code is None:
            return []

        return slice_recent([row_to_client_type(row) for row in rows], limit)

    def query_readonly(
        self,
        sql: str,
        params: Mapping[str, Any] | Sequence[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a validated read-only query (``SELECT``/``WITH``/``PRAGMA``) on ``?mode=ro``."""
        cleaned_sql = validate_readonly_sql(sql, allow_pragma=True)
        bound_params: Mapping[str, Any] | tuple[Any, ...]
        if params is None:
            bound_params = ()
        elif isinstance(params, Mapping):
            bound_params = dict(params)
        else:
            bound_params = tuple(params)

        with self._lock:
            self._ensure_open()
            if self._is_memory:
                try:
                    self._conn.execute("PRAGMA query_only = ON")
                    cursor = self._conn.execute(cleaned_sql, bound_params)
                    if cursor.description is None:
                        return []
                    columns = [col[0] for col in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
                except sqlite3.Error as exc:
                    raise StorageError(f"Read-only query failed: {exc}") from exc
                finally:
                    try:
                        self._conn.execute("PRAGMA query_only = OFF")
                    except sqlite3.Error:
                        pass

            assert self.path is not None
            ro_uri = f"{self.path.resolve().as_uri()}?mode=ro"
            ro_conn: sqlite3.Connection | None = None
            try:
                ro_conn = sqlite3.connect(ro_uri, uri=True, timeout=self._timeout)
                ro_conn.execute("PRAGMA foreign_keys = ON")
                cursor = ro_conn.execute(cleaned_sql, bound_params)
                if cursor.description is None:
                    return []
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            except sqlite3.Error as exc:
                raise StorageError(f"Read-only query failed: {exc}") from exc
            finally:
                if ro_conn is not None:
                    ro_conn.close()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_open()
            try:
                summary: dict[str, Any] = {
                    "backend": "sqlite",
                    "dialect": "sqlite",
                    "schema_version": int(self._conn.execute("PRAGMA user_version").fetchone()[0]),
                }
                for table in TABLE_NAMES:
                    summary[table] = int(
                        self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    )

                price_bounds = self._conn.execute(
                    "SELECT MIN(date) AS min_d, MAX(date) AS max_d FROM daily_prices"
                ).fetchone()
                ct_bounds = self._conn.execute(
                    "SELECT MIN(date) AS min_d, MAX(date) AS max_d FROM client_types"
                ).fetchone()
                summary["min_price_date"] = price_bounds["min_d"] if price_bounds else None
                summary["max_price_date"] = price_bounds["max_d"] if price_bounds else None
                summary["min_client_type_date"] = ct_bounds["min_d"] if ct_bounds else None
                summary["max_client_type_date"] = ct_bounds["max_d"] if ct_bounds else None
                summary["last_sectors_sync"] = self.get_sync_meta("last_sectors_sync")
                summary["last_instruments_sync"] = self.get_sync_meta("last_instruments_sync")
                return summary
            except sqlite3.Error as exc:
                raise StorageError(f"Failed to compute SQLite storage stats: {exc}") from exc
