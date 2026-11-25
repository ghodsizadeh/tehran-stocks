"""Tests for SQLiteStore, SQLAlchemyStore, open_store, and SyncService/AsyncSyncService."""

from __future__ import annotations

import asyncio
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.parse import unquote

import httpx2
import pytest

from tehran_stocks.client import AsyncClient
from tehran_stocks.exceptions import StorageError, TSETMCError
from tehran_stocks.storage import (
    AsyncSyncService,
    SQLAlchemyStore,
    SQLiteStore,
    StorageBackend,
    SyncProgress,
    SyncResult,
    SyncService,
    open_store,
)
from tehran_stocks.types import (
    ClientTypeDaily,
    DailyBar,
    Instrument,
    PriceAdjustment,
    Sector,
    ShareChange,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
KGL_INS_CODE = "35700344742885862"
KAZER_INS_CODE = "49353447565507376"
BEMAN_INS_CODE = "52551569846042389"


def _load_fixture(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _make_store(kind: str, tmp_path: Path) -> SQLiteStore | SQLAlchemyStore:
    if kind == "sqlite_file":
        return SQLiteStore(tmp_path / "market.db")
    if kind == "sqlite_memory":
        return SQLiteStore(":memory:")
    if kind == "sqlalchemy_file":
        return SQLAlchemyStore(f"sqlite:///{tmp_path / 'sqla_market.db'}")
    if kind == "sqlalchemy_memory":
        return SQLAlchemyStore("sqlite:///:memory:")
    raise AssertionError(f"Unknown store kind: {kind}")


def _make_sync_transport(
    call_log: list[str] | None = None,
    *,
    in_flight_tracker: dict[str, int] | None = None,
    delay: float = 0.0,
    failing_ins_codes: set[str] | None = None,
) -> httpx2.MockTransport:
    static_data = _load_fixture("static_data.json")
    market_watch = _load_fixture("market_watch.json")
    # Include کگل in sector 13 inside a copy of market_watch for sector/all sync tests
    watch_rows = list(market_watch["marketwatch"]) + [
        {
            "lva": "كگل",
            "lvc": "معدني و صنعتي گل گهر",
            "flow": 1,
            "csv": "13 ",
            "insID": "IRO1GOLG0005",
            "ztd": 655000000000.0,
            "insCode": KGL_INS_CODE,
            "pdv": 4120.0,
            "pcl": 4110.0,
            "py": 4000.0,
            "pf": 4090.0,
            "pmx": 4120.0,
            "pmn": 4000.0,
            "qtj": 441108505.0,
            "qtc": 1814088254160.0,
            "ztt": 4608.0,
        }
    ]
    watch_payload = {"marketwatch": watch_rows}
    search_payload = _load_fixture("search.json")
    daily_payload = _load_fixture("daily_history.json")
    adj_payload = _load_fixture("price_adjustments.json")
    share_payload = _load_fixture("share_changes.json")
    ct_hist_payload = _load_fixture("client_type_history.json")

    def _clone_rows_for_ins(rows: list[dict[str, Any]], ins_code: str) -> list[dict[str, Any]]:
        return [{**row, "insCode": ins_code} for row in rows]

    async def handler(request: httpx2.Request) -> httpx2.Response:
        path = unquote(request.url.path)
        if call_log is not None:
            call_log.append(path)

        if in_flight_tracker is not None:
            in_flight_tracker["current"] += 1
            in_flight_tracker["max"] = max(in_flight_tracker["max"], in_flight_tracker["current"])

        try:
            if delay > 0:
                await asyncio.sleep(delay)

            if path == "/api/StaticData/GetStaticData":
                return httpx2.Response(200, json=static_data)

            if path == "/api/ClosingPrice/GetMarketWatch":
                return httpx2.Response(200, json=watch_payload)

            if path.startswith("/api/Instrument/GetInstrumentSearch/"):
                query = path.removeprefix("/api/Instrument/GetInstrumentSearch/")
                if query in ("ناموجود", "MISSING_SYM"):
                    return httpx2.Response(200, json={"instrumentSearch": []})
                return httpx2.Response(200, json=search_payload)

            if path.startswith("/api/ClosingPrice/GetClosingPriceDailyList/"):
                rest = path.removeprefix("/api/ClosingPrice/GetClosingPriceDailyList/")
                ins_code, days_str = rest.split("/", 1)
                if failing_ins_codes and ins_code in failing_ins_codes:
                    return httpx2.Response(500, json={"error": "upstream failure"})
                days = int(days_str)
                rows = daily_payload["closingPriceDaily"]
                selected = rows if days == 0 else rows[:days]
                return httpx2.Response(
                    200,
                    json={"closingPriceDaily": _clone_rows_for_ins(selected, ins_code)},
                )

            if path.startswith("/api/ClosingPrice/GetPriceAdjustList/"):
                ins_code = path.removeprefix("/api/ClosingPrice/GetPriceAdjustList/")
                if failing_ins_codes and ins_code in failing_ins_codes:
                    return httpx2.Response(500, json={"error": "upstream failure"})
                if ins_code == KGL_INS_CODE:
                    return httpx2.Response(200, json=adj_payload)
                return httpx2.Response(200, json={"priceAdjust": []})

            if path.startswith("/api/Instrument/GetInstrumentShareChange/"):
                ins_code = path.removeprefix("/api/Instrument/GetInstrumentShareChange/")
                if ins_code == KGL_INS_CODE:
                    return httpx2.Response(200, json=share_payload)
                return httpx2.Response(200, json={"instrumentShareChange": []})

            if path.startswith("/api/ClientType/GetClientTypeHistory/"):
                ins_code = path.removeprefix("/api/ClientType/GetClientTypeHistory/")
                if failing_ins_codes and ins_code in failing_ins_codes:
                    return httpx2.Response(500, json={"error": "upstream failure"})
                return httpx2.Response(
                    200,
                    json={
                        "clientType": _clone_rows_for_ins(ct_hist_payload["clientType"], ins_code)
                    },
                )

            return httpx2.Response(404, json={"error": f"Unhandled path: {path}"})
        finally:
            if in_flight_tracker is not None:
                in_flight_tracker["current"] -= 1

    return httpx2.MockTransport(handler)


def test_storage_zero_import_side_effects(tmp_path: Path) -> None:
    src_dir = Path(__file__).resolve().parents[2] / "src"
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "PYTHONPATH": str(src_dir),
    }
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from tehran_stocks import storage; assert hasattr(storage, 'open_store')",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout == ""
    assert proc.stderr == ""
    assert list(tmp_path.iterdir()) == []


def _delete_mode_db(path: Path) -> bytes:
    """Create an initialized database switched back to DELETE mode; return its bytes."""
    import sqlite3

    SQLiteStore(path).close()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode = DELETE")
    conn.close()
    return path.read_bytes()


def test_read_only_store_leaves_the_file_and_its_journal_mode_alone(tmp_path: Path) -> None:
    # Opening a store switched the file to WAL even when it was only queried (#125).
    db_path = tmp_path / "journal-test.sqlite"
    before = _delete_mode_db(db_path)

    with SQLiteStore(db_path, read_only=True) as store:
        assert store.query_readonly("SELECT 1 AS n") == [{"n": 1}]
        assert store.query_readonly("PRAGMA journal_mode")[0]["journal_mode"].lower() == "delete"
        assert store.stats()["schema_version"] == 1

    assert db_path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["journal-test.sqlite"]


def test_read_only_store_does_not_create_a_missing_file(tmp_path: Path) -> None:
    db_path = tmp_path / "missing" / "tse.db"
    with pytest.raises(StorageError, match="not found"):
        SQLiteStore(db_path, read_only=True)
    assert not db_path.parent.exists()


def test_open_store_read_only_routes_to_a_read_only_sqlite_store(tmp_path: Path) -> None:
    db_path = tmp_path / "tse.db"
    before = _delete_mode_db(db_path)
    store = open_store(str(db_path), init_schema=True, read_only=True)
    try:
        assert store.query_readonly("SELECT COUNT(*) AS n FROM instruments") == [{"n": 0}]
    finally:
        store.close()
    assert db_path.read_bytes() == before


def test_sqlite_store_pragmas_schema_version_and_lifecycle(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "tse.db"
    with SQLiteStore(db_path) as store:
        assert isinstance(store, StorageBackend)
        assert db_path.exists()

        jm = store.query_readonly("PRAGMA journal_mode")
        assert jm[0]["journal_mode"].lower() == "wal"

        fk = store.query_readonly("PRAGMA foreign_keys")
        assert fk[0]["foreign_keys"] == 1

        uv = store.query_readonly("PRAGMA user_version")
        assert uv[0]["user_version"] == 1

        # Re-running init_schema is idempotent
        store.init_schema()
        stats = store.stats()
        assert stats["backend"] == "sqlite"
        assert stats["schema_version"] == 1
        assert stats["daily_prices"] == 0

    with pytest.raises(StorageError, match="closed"):
        store.stats()


@pytest.mark.parametrize(
    "kind",
    ["sqlite_file", "sqlite_memory", "sqlalchemy_file", "sqlalchemy_memory"],
)
def test_upserts_idempotency_persian_lookup_and_queries(kind: str, tmp_path: Path) -> None:
    daily_rows = _load_fixture("daily_history.json")["closingPriceDaily"]
    adj_rows = _load_fixture("price_adjustments.json")["priceAdjust"]
    ct_rows = _load_fixture("client_type_history.json")["clientType"]
    share_rows = _load_fixture("share_changes.json")["instrumentShareChange"]

    bars = [DailyBar.from_tsetmc(r, ins_code=KGL_INS_CODE) for r in daily_rows]
    adjs = [PriceAdjustment.from_tsetmc(r, ins_code=KGL_INS_CODE) for r in adj_rows]
    cts = [
        ClientTypeDaily.from_tsetmc(
            {
                **r,
                "buy_i_count": r.get("buy_I_Count"),
                "sell_i_count": r.get("sell_I_Count"),
                "buy_n_count": r.get("buy_N_Count"),
                "sell_n_count": r.get("sell_N_Count"),
            },
            ins_code=KGL_INS_CODE,
        )
        for r in ct_rows
    ]
    changes = [ShareChange.from_tsetmc(r, ins_code=KGL_INS_CODE) for r in share_rows]

    sectors = [
        Sector(code="1", name="زراعت و خدمات وابسته", type="IndustrialGroup"),
        Sector(code="13 ", name="استخراج كانه هاي فلزي", type="IndustrialGroup"),
    ]
    instruments = [
        Instrument(
            ins_code=KGL_INS_CODE,
            symbol="كگل",  # Arabic Kaf deliberately supplied
            name="معدني و صنعتي گل گهر",
            isin="IRO1GOLG0005",
            instrument_id="IRO1GOLG0001",
            market="بازار بورس",
            flow=1,
            sector_code="13",
            sector_name="استخراج كانه هاي فلزي",
            total_shares=655_000_000_000,
        ),
        Instrument(
            ins_code="99999999999999991",
            symbol="فولاد",
            name="اختیار معامله فولاد",
            flow=3,
            sector_code="27",
            total_shares=0,
        ),
        Instrument(
            ins_code="46348559193224090",
            symbol="فولاد",
            name="فولاد مبارکه اصفهان",
            flow=1,
            sector_code="27",
            total_shares=500_000_000_000,
        ),
    ]

    with _make_store(kind, tmp_path) as store:
        assert isinstance(store, StorageBackend)
        assert store.upsert_sectors(sectors) == 2
        assert store.upsert_instruments(instruments) == 3
        assert store.upsert_prices(bars) == 15
        assert store.upsert_adjustments(adjs) == 15
        assert store.upsert_client_types(cts) == 15
        assert store.upsert_share_changes(changes) == 15

        # Idempotent re-upsert with duplicate batch items and updated close on latest bar
        updated_latest = DailyBar(
            ins_code=KGL_INS_CODE,
            date=date(2026, 11, 22),
            open=3880.0,
            high=4050.0,
            low=3880.0,
            close=4010.0,
            last=3990.0,
            yesterday=3930.0,
            volume=424066991,
            value=1694823471830,
            trade_count=5074,
        )
        assert store.upsert_prices([updated_latest, updated_latest]) == 1
        assert store.upsert_adjustments(adjs) == 15

        stats = store.stats()
        assert stats["sectors"] == 2
        assert stats["instruments"] == 3
        assert stats["daily_prices"] == 15
        # Both same-day events on 2018-07-03 from real fixture must be preserved
        assert stats["price_adjustments"] == 15
        assert stats["client_types"] == 15
        assert stats["share_changes"] == 15
        assert stats["min_price_date"] == "2026-11-02"
        assert stats["max_price_date"] == "2026-11-22"

        # Verify both 2018-07-03 adjustment events came back intact
        stored_adjs = store.get_adjustments("کگل")
        assert len(stored_adjs) == 15
        july3 = [a for a in stored_adjs if a.date == date(2018, 7, 3)]
        assert len(july3) == 2

        # Persian/Arabic normalization, ISIN, and flow-prioritized symbol resolution
        assert store.resolve_ins_code("کگل") == KGL_INS_CODE
        assert store.resolve_ins_code("كگل") == KGL_INS_CODE
        assert store.resolve_ins_code("۳۵۷۰۰۳۴۴۷۴۲۸۸۵۸۶۲") == KGL_INS_CODE
        assert store.resolve_ins_code("iro1golg0005") == KGL_INS_CODE
        assert store.resolve_ins_code("فولاد") == "46348559193224090"
        assert store.resolve_ins_code("ناموجود") is None

        # list_instruments filters
        assert len(store.list_instruments(sector_code="13 ")) == 1
        assert len(store.list_instruments(query="معدني")) == 1
        assert store.list_instruments(query="معدني")[0].symbol == "کگل"
        assert len(store.list_instruments(flow=1, limit=1)) == 1
        assert store.list_instruments(limit=0) == []

        # Price queries with Gregorian & Jalali dates and limit
        assert store.get_last_price_date("كگل") == date(2026, 11, 22)
        assert store.get_last_client_type_date("کگل") == date(2026, 11, 22)

        all_bars = store.get_prices("کگل")
        assert len(all_bars) == 15
        assert all_bars[-1].close == pytest.approx(4010.0)

        # 2026-11-17 == 1405-08-26 in Jalali
        jalali_filtered = store.get_prices("کگل", start="1405-08-26", end="2026-11-21")
        assert [b.date for b in jalali_filtered] == [
            date(2026, 11, 17),
            date(2026, 11, 18),
            date(2026, 11, 21),
        ]

        limited = store.get_prices("کگل", limit=3)
        assert [b.date for b in limited] == [
            date(2026, 11, 18),
            date(2026, 11, 21),
            date(2026, 11, 22),
        ]

        # Client type queries preserve real_money_flow / buyer_power
        ct_recent = store.get_client_types("كگل", limit=2)
        assert len(ct_recent) == 2
        assert ct_recent[-1].date == date(2026, 11, 22)
        assert ct_recent[-1].real_money_flow == 681368933310 - 550052671100
        assert ct_recent[-1].buyer_power == pytest.approx(
            (681368933310 / 1022) / (550052671100 / 796)
        )


@pytest.mark.parametrize(
    "kind",
    ["sqlite_file", "sqlite_memory", "sqlalchemy_file", "sqlalchemy_memory"],
)
def test_get_prices_adjusted_true_across_backends(kind: str, tmp_path: Path) -> None:
    daily_rows = _load_fixture("daily_history.json")["closingPriceDaily"]
    bars = [DailyBar.from_tsetmc(r, ins_code=KGL_INS_CODE) for r in daily_rows]
    # Add a 2:1 corporate-action event mid-series on 2026-11-15
    adj = PriceAdjustment(
        ins_code=KGL_INS_CODE,
        date=date(2026, 11, 15),
        adjusted_close=2000.0,
        unadjusted_close=4000.0,
        corporate_type_code=1,
    )

    with _make_store(kind, tmp_path) as store:
        store.upsert_prices(bars)
        store.upsert_adjustments([adj])

        # Direct numeric insCode works even without instruments metadata populated
        raw = store.get_prices(KGL_INS_CODE, adjusted=False)
        adjusted = store.get_prices(KGL_INS_CODE, adjusted=True)
        assert len(raw) == len(adjusted) == 15
        assert adjusted[0].date == date(2026, 11, 2)
        assert adjusted[0].close == pytest.approx(raw[0].close * 0.5)
        assert adjusted[0].volume == raw[0].volume
        assert adjusted[-1].date == date(2026, 11, 22)
        assert adjusted[-1].close == pytest.approx(raw[-1].close)

        # Even if end precedes the adjustment event, backward scaling still applies!
        early_adjusted = store.get_prices(KGL_INS_CODE, end=date(2026, 11, 10), adjusted=True)
        assert len(early_adjusted) > 0
        assert early_adjusted[0].close == pytest.approx(raw[0].close * 0.5)


@pytest.mark.parametrize(
    "kind",
    ["sqlite_file", "sqlite_memory", "sqlalchemy_file"],
)
def test_readonly_sql_enforcement(kind: str, tmp_path: Path) -> None:
    with _make_store(kind, tmp_path) as store:
        store.upsert_sectors([Sector(code="13", name="استخراج کانه های فلزی")])
        store.upsert_instruments(
            [Instrument(ins_code=KGL_INS_CODE, symbol="کگل", name="گل گهر", sector_code="13")]
        )

        # Valid SELECT and WITH queries work (with literals containing keywords/semicolons)
        rows = store.query_readonly(
            "SELECT ins_code, symbol, 'DELETE; DROP' AS literal FROM instruments WHERE symbol = :sym;",
            {"sym": "کگل"},
        )
        assert len(rows) == 1
        assert rows[0]["ins_code"] == KGL_INS_CODE
        assert rows[0]["literal"] == "DELETE; DROP"

        cte_rows = store.query_readonly(
            "/* safe cte */ WITH inst AS (SELECT symbol, sector_code FROM instruments) "
            "SELECT * FROM inst WHERE sector_code = ?",
            ("13",),
        )
        assert cte_rows == [{"symbol": "کگل", "sector_code": "13"}]

        # SQLiteStore allows allowlisted read-only PRAGMAs; SQLAlchemyStore restricts to SELECT/WITH
        if isinstance(store, SQLiteStore):
            info = store.query_readonly("PRAGMA table_info(instruments)")
            assert any(col["name"] == "ins_code" for col in info)
            assert store.query_readonly("PRAGMA user_version")[0]["user_version"] == 1
            for bad_pragma in (
                "PRAGMA user_version = 99",
                "PRAGMA user_version(99)",
                "PRAGMA query_only(0)",
                "PRAGMA writable_schema = ON",
                "PRAGMA writable_schema(1)",
                "PRAGMA cache_size = 100",
            ):
                with pytest.raises(StorageError):
                    store.query_readonly(bad_pragma)
        else:
            with pytest.raises(StorageError):
                store.query_readonly("PRAGMA table_info(instruments)")

        forbidden_queries = [
            "",
            "   ",
            "INSERT INTO sectors VALUES ('99', 'test', '', '', 0, 0, 0, 0)",
            "UPDATE instruments SET symbol = 'X'",
            "DELETE FROM instruments",
            "DROP TABLE instruments",
            "ALTER TABLE instruments ADD COLUMN extra TEXT",
            "CREATE TABLE evil (id INTEGER)",
            "REPLACE INTO sectors (code, name) VALUES ('99', 'evil')",
            "VACUUM",
            "ATTACH DATABASE ':memory:' AS aux",
            "SELECT 1; DROP TABLE instruments",
            "-- hidden comment\nDELETE FROM instruments",
            "WITH x AS (SELECT 1) DELETE FROM instruments",
            "SELECT 'unterminated",
        ]
        for bad_sql in forbidden_queries:
            with pytest.raises(StorageError):
                store.query_readonly(bad_sql)


def test_cross_backend_sqlite_file_interoperability(tmp_path: Path) -> None:
    db_path = tmp_path / "shared.db"
    daily_rows = _load_fixture("daily_history.json")["closingPriceDaily"]
    bars = [DailyBar.from_tsetmc(r, ins_code=KGL_INS_CODE) for r in daily_rows]

    with SQLiteStore(db_path) as sqlite_store:
        sqlite_store.upsert_instruments(
            [Instrument(ins_code=KGL_INS_CODE, symbol="کگل", name="گل گهر", sector_code="13")]
        )
        sqlite_store.upsert_prices(bars)

    with SQLAlchemyStore(f"sqlite:///{db_path}") as sqla_store:
        assert sqla_store.resolve_ins_code("کگل") == KGL_INS_CODE
        read_bars = sqla_store.get_prices("کگل")
        assert len(read_bars) == 15
        assert read_bars[-1].date == date(2026, 11, 22)
        assert sqla_store.stats()["daily_prices"] == 15


def test_open_store_routing_and_missing_driver_hints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s1 = open_store(tmp_path / "local.db")
    assert isinstance(s1, SQLiteStore)
    s1.close()

    s2 = open_store(str(tmp_path / "other.sqlite"))
    assert isinstance(s2, SQLiteStore)
    s2.close()

    s3 = open_store(":memory:")
    assert isinstance(s3, SQLiteStore)
    s3.close()

    s4 = open_store(f"sqlite:///{tmp_path / 'url.db'}")
    assert isinstance(s4, SQLiteStore)
    s4.close()

    s5 = open_store("sqlite:///:memory:")
    assert isinstance(s5, SQLiteStore)
    s5.close()

    s6 = open_store(tmp_path / "forced_sqla.db", backend="sqlalchemy")
    assert isinstance(s6, SQLAlchemyStore)
    assert s6.dialect_name == "sqlite"
    s6.close()

    s7 = open_store("sqlite+pysqlite:///:memory:")
    assert isinstance(s7, SQLAlchemyStore)
    s7.close()

    with pytest.raises(StorageError):
        open_store("postgresql://user:pass@localhost/tse", backend="sqlite")
    with pytest.raises(StorageError):
        open_store("market.db", backend="invalid-backend")
    with pytest.raises(StorageError):
        open_store("   ")

    # Simulate missing optional native DB drivers and verify helpful install hints
    def _fail_create_engine(url: str, **_kwargs: Any) -> Any:
        if "postgres" in url:
            raise ModuleNotFoundError("No module named 'psycopg2'")
        if "duckdb" in url:
            raise ModuleNotFoundError("No module named 'duckdb_engine'")
        raise ModuleNotFoundError("No module named 'unknown_driver'")

    monkeypatch.setattr("tehran_stocks.storage.sqlalchemy.create_engine", _fail_create_engine)

    with pytest.raises(StorageError, match="tehran-stocks\\[postgres\\]"):
        open_store("postgresql://user:pass@localhost:5432/tse")

    with pytest.raises(StorageError, match="tehran-stocks\\[duckdb\\]"):
        open_store("duckdb:///market.duckdb")


def test_sync_service_instruments_and_incremental_syncs(tmp_path: Path) -> None:
    calls: list[str] = []
    transport = _make_sync_transport(calls)
    progress_events: list[SyncProgress] = []

    with open_store(tmp_path / "sync.db") as store:
        sync = SyncService(store, transport=transport, retry_backoff=0.0)

        # 1) Sync sectors + instruments in EXACTLY 2 HTTP calls
        inst_res = sync.sync_instruments(on_progress=progress_events.append)
        assert isinstance(inst_res, SyncResult)
        assert len(calls) == 2
        assert set(calls) == {"/api/StaticData/GetStaticData", "/api/ClosingPrice/GetMarketWatch"}
        assert inst_res.sectors > 0
        assert inst_res.instruments == 13  # 12 fixture rows + injected کگل row

        # Normalized Persian symbol & enriched sector_name
        assert store.resolve_ins_code("کاذر") == KAZER_INS_CODE
        assert store.resolve_ins_code("کگل") == KGL_INS_CODE
        kgl = store.list_instruments(query="کگل")[0]
        assert kgl.sector_code == "13"
        assert kgl.sector_name == "استخراج کانه های فلزی"

        # 2) Incremental daily_prices sync: seed first 10 bars, then sync missing 5
        daily_rows = _load_fixture("daily_history.json")["closingPriceDaily"]
        all_bars = sorted(
            (DailyBar.from_tsetmc(r, ins_code=KGL_INS_CODE) for r in daily_rows),
            key=lambda b: b.date,
        )
        store.upsert_prices(all_bars[:10])
        assert store.get_last_price_date("کگل") == all_bars[9].date

        p_res = sync.sync_prices(["کگل"], incremental=True, on_progress=progress_events.append)
        assert p_res.prices == 5
        assert p_res.adjustments == 15
        assert p_res.errors == {}
        assert len(store.get_prices("کگل")) == 15

        # Second incremental sync writes 0 new price bars
        p_res2 = sync.sync_prices(["کگل"], incremental=True)
        assert p_res2.prices == 0
        assert p_res2.skipped_symbols == 1

        # 3) Incremental client_types sync: seed first 10 days, then sync missing 5
        ct_rows = _load_fixture("client_type_history.json")["clientType"]
        all_cts = sorted(
            (
                ClientTypeDaily.from_tsetmc(
                    {
                        **r,
                        "buy_i_count": r.get("buy_I_Count"),
                        "sell_i_count": r.get("sell_I_Count"),
                        "buy_n_count": r.get("buy_N_Count"),
                        "sell_n_count": r.get("sell_N_Count"),
                    },
                    ins_code=KGL_INS_CODE,
                )
                for r in ct_rows
            ),
            key=lambda c: c.date,
        )
        store.upsert_client_types(all_cts[:10])
        ct_res = sync.sync_client_types(["کگل"], incremental=True)
        assert ct_res.client_types == 5
        assert len(store.get_client_types("کگل")) == 15

        ct_res2 = sync.sync_client_types(["کگل"], incremental=True)
        assert ct_res2.client_types == 0

        # 4) Sync by sector & all_instruments
        sec_res = sync.sync_prices(sector="13", incremental=False)
        assert sec_res.prices == 15
        assert sec_res.synced_symbols == 1

        assert sync.sync_prices([]).prices == 0
        with pytest.raises(ValueError, match="Specify at least one"):
            sync.sync_prices()

        all_res = sync.sync_all(all_instruments=True, incremental=True, include_client_types=True)
        assert all_res.instruments == 13
        # Remaining 12 instruments (excluding already up-to-date کگل) get 15 bars & 15 ct rows each
        assert all_res.prices == 12 * 15
        assert all_res.client_types == 12 * 15
        assert any(evt.stage == "instruments" for evt in progress_events)
        assert any(evt.stage == "prices" for evt in progress_events)


@pytest.mark.asyncio
async def test_async_sync_service_concurrency_and_error_handling(tmp_path: Path) -> None:
    tracker = {"current": 0, "max": 0}
    transport = _make_sync_transport(
        in_flight_tracker=tracker,
        delay=0.01,
        failing_ins_codes={BEMAN_INS_CODE},
    )

    with open_store(tmp_path / "async_sync.db") as store:
        # Calling SyncService inside a running event loop fails cleanly
        sync_facade = SyncService(store, transport=transport)
        with pytest.raises(StorageError, match="AsyncSyncService"):
            sync_facade.sync_instruments()

        async with AsyncClient(
            transport=transport,
            max_concurrency=2,
            retry_backoff=0.0,
        ) as client:
            async_sync = AsyncSyncService(store, client=client, max_concurrency=2)
            await async_sync.sync_instruments()

            # Sync all instruments: 12 succeed, 1 fails (BEMAN_INS_CODE -> 500)
            res = await async_sync.sync_prices(
                all_instruments=True,
                include_adjustments=False,
                fail_fast=False,
            )
            assert tracker["max"] <= 2
            assert res.synced_symbols == 12
            assert len(res.errors) == 1
            assert "بمان" in res.errors

            # Missing symbol recorded in errors when fail_fast=False, raises when fail_fast=True
            err_res = await async_sync.sync_prices(["MISSING_SYM"], fail_fast=False)
            assert "MISSING_SYM" in err_res.errors

            with pytest.raises(StorageError):
                await async_sync.sync_prices(["MISSING_SYM"], fail_fast=True)


@pytest.mark.asyncio
async def test_async_sync_service_fail_fast_cancels_and_awaits_sibling_workers(
    tmp_path: Path,
) -> None:
    daily_rows = _load_fixture("daily_history.json")["closingPriceDaily"]
    sym2_started = asyncio.Event()
    sym2_release = asyncio.Event()
    sym2_cancelled = False
    sym2_finished = False
    sym2_returned = False

    async def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal sym2_cancelled, sym2_finished, sym2_returned
        path = unquote(request.url.path)

        if path.startswith(f"/api/ClosingPrice/GetClosingPriceDailyList/{BEMAN_INS_CODE}/"):
            sym2_started.set()
            try:
                await sym2_release.wait()
                sym2_returned = True
                return httpx2.Response(
                    200,
                    json={
                        "closingPriceDaily": [
                            {**row, "insCode": BEMAN_INS_CODE} for row in daily_rows
                        ]
                    },
                )
            except asyncio.CancelledError:
                sym2_cancelled = True
                raise
            finally:
                sym2_finished = True

        if path.startswith(f"/api/ClosingPrice/GetClosingPriceDailyList/{KGL_INS_CODE}/"):
            await sym2_started.wait()
            return httpx2.Response(500, json={"error": "upstream failure"})

        return httpx2.Response(404, json={"error": f"Unhandled path: {path}"})

    transport = httpx2.MockTransport(handler)
    with open_store(tmp_path / "fail_fast_cancel.db") as store:
        store.upsert_instruments(
            [
                Instrument(ins_code=KGL_INS_CODE, symbol="کگل", name="گل گهر"),
                Instrument(ins_code=BEMAN_INS_CODE, symbol="بمان", name="بازده مانا"),
            ]
        )

        async with AsyncClient(
            transport=transport,
            max_concurrency=2,
            max_retries=0,
            retry_backoff=0.0,
        ) as client:
            async_sync = AsyncSyncService(store, client=client, max_concurrency=2)
            with pytest.raises(TSETMCError):
                await async_sync.sync_prices(
                    ["کگل", "بمان"],
                    include_adjustments=False,
                    fail_fast=True,
                )

            # Sibling worker 2 must be cancelled and awaited before sync_prices returns.
            assert sym2_started.is_set()
            assert sym2_cancelled is True
            assert sym2_finished is True
            assert sym2_returned is False
            assert store.get_prices(BEMAN_INS_CODE) == []
            assert store.stats()["daily_prices"] == 0

            # Unblocking the event afterward must not trigger any late writes.
            sym2_release.set()
            await asyncio.sleep(0)
            assert sym2_returned is False
            assert store.get_prices(BEMAN_INS_CODE) == []
            assert store.stats()["daily_prices"] == 0
