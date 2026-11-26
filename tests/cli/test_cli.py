"""Tests for the ``tse`` Typer CLI using CliRunner, httpx2.MockTransport, and SQLite."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import types
from typing import Any
from urllib.parse import unquote

import httpx2
import pytest
from typer.testing import CliRunner

import tehran_stocks.cli as cli_mod
from tehran_stocks.cli import app

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
KGL_INS_CODE = "35700344742885862"
ETF_INS_CODE = "52551569846042389"
TEDPIX_INS_CODE = "32097828799138957"

runner = CliRunner()


def _load_fixture(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _make_tsetmc_router(
    call_log: list[str] | None = None,
    *,
    extra_routes: dict[str, Any] | None = None,
) -> httpx2.MockTransport:
    """Build an httpx2.MockTransport routing cdn.tsetmc.com endpoints to real JSON fixtures."""
    fixtures = {
        "search": _load_fixture("search.json"),
        "info": _load_fixture("instrument_info.json"),
        "identity": _load_fixture("instrument_identity.json"),
        "stats": _load_fixture("instrument_stats.json"),
        "share_changes": _load_fixture("share_changes.json"),
        "quote": _load_fixture("quote.json"),
        "daily_history": _load_fixture("daily_history.json"),
        "price_adjustments": _load_fixture("price_adjustments.json"),
        "orderbook": _load_fixture("orderbook.json"),
        "intraday": _load_fixture("intraday.json"),
        "client_type_live": _load_fixture("client_type_live.json"),
        "client_type_history": _load_fixture("client_type_history.json"),
        "client_type_all": _load_fixture("client_type_all.json"),
        "market_watch": _load_fixture("market_watch.json"),
        "static_data": _load_fixture("static_data.json"),
        "sectors_summary": _load_fixture("sectors_summary.json"),
        "market_overview": _load_fixture("market_overview.json"),
        "indices": _load_fixture("indices.json"),
        "index_history": _load_fixture("index_history.json"),
        "shareholders": _load_fixture("shareholders.json"),
        "codal": _load_fixture("codal.json"),
        "messages": _load_fixture("messages.json"),
        "etf": _load_fixture("etf.json"),
        "options_watch": _load_fixture("options_watch.json"),
    }

    static_map: dict[str, Any] = {
        f"/api/Instrument/GetInstrumentInfo/{KGL_INS_CODE}": fixtures["info"],
        f"/api/Instrument/GetInstrumentInfo/{ETF_INS_CODE}": fixtures["info"],
        f"/api/Instrument/GetInstrumentIdentity/{KGL_INS_CODE}": fixtures["identity"],
        f"/api/MarketData/GetInstrumentStatistic/{KGL_INS_CODE}": fixtures["stats"],
        f"/api/Instrument/GetInstrumentShareChange/{KGL_INS_CODE}": fixtures["share_changes"],
        f"/api/ClosingPrice/GetClosingPriceInfo/{KGL_INS_CODE}": fixtures["quote"],
        f"/api/ClosingPrice/GetPriceAdjustList/{KGL_INS_CODE}": fixtures["price_adjustments"],
        f"/api/BestLimits/{KGL_INS_CODE}": fixtures["orderbook"],
        f"/api/ClientType/GetClientType/{KGL_INS_CODE}/1/0": fixtures["client_type_live"],
        f"/api/ClientType/GetClientTypeHistory/{KGL_INS_CODE}": fixtures["client_type_history"],
        "/api/ClientType/GetClientTypeAll": fixtures["client_type_all"],
        "/api/ClosingPrice/GetMarketWatch": fixtures["market_watch"],
        "/api/MarketData/GetMarketOverview/1": fixtures["market_overview"],
        "/api/MarketData/GetSectorsSummary": fixtures["sectors_summary"],
        "/api/StaticData/GetStaticData": fixtures["static_data"],
        "/api/Index/GetIndexB1LastAll/All/1": fixtures["indices"],
        f"/api/Index/GetIndexB2History/{TEDPIX_INS_CODE}": fixtures["index_history"],
        f"/api/Shareholder/GetInstrumentShareHolderLast/{KGL_INS_CODE}": fixtures["shareholders"],
        f"/api/Codal/GetPreparedDataByInsCode/10/{KGL_INS_CODE}": fixtures["codal"],
        f"/api/Codal/GetPreparedDataByInsCode/3/{KGL_INS_CODE}": {
            "preparedData": fixtures["codal"]["preparedData"][:3]
        },
        f"/api/Msg/GetMsgByInsCode/{KGL_INS_CODE}": fixtures["messages"],
        f"/api/Fund/GetETFByInsCode/{ETF_INS_CODE}": fixtures["etf"],
        "/api/Instrument/GetInstrumentOptionMarketWatch/1": fixtures["options_watch"],
    }
    if extra_routes:
        static_map.update(extra_routes)

    def handler(request: httpx2.Request) -> httpx2.Response:
        path = unquote(request.url.path)
        if call_log is not None:
            call_log.append(path)

        if path in static_map:
            payload = static_map[path]
            if callable(payload):
                return payload(request)
            return httpx2.Response(200, json=payload)

        daily_prefix = f"/api/ClosingPrice/GetClosingPriceDailyList/{KGL_INS_CODE}/"
        if path.startswith(daily_prefix):
            days_str = path.removeprefix(daily_prefix)
            if days_str.isdigit():
                days = int(days_str)
                rows = fixtures["daily_history"]["closingPriceDaily"]
                selected = rows if days == 0 else rows[:days]
                return httpx2.Response(200, json={"closingPriceDaily": selected})

        if path.startswith("/api/Instrument/GetInstrumentSearch/"):
            query = path.removeprefix("/api/Instrument/GetInstrumentSearch/")
            if query in ("ناموجود", "NOT_FOUND_XYZ"):
                return httpx2.Response(200, json={"instrumentSearch": []})
            if query == "بمان":
                return httpx2.Response(
                    200,
                    json={
                        "instrumentSearch": [
                            {
                                "insCode": ETF_INS_CODE,
                                "lVal18AFC": "بمان",
                                "lVal30": "صندوق س.بازده مانا-د",
                                "flow": 2,
                                "flowTitle": "بازار فرابورس",
                                "cgrValCot": "1A",
                                "lastDate": 1,
                            }
                        ]
                    },
                )
            return httpx2.Response(200, json=fixtures["search"])

        return httpx2.Response(404, json={"error": f"Unhandled path: {path}"})

    return httpx2.MockTransport(handler)


def _invoke(
    args: list[str],
    *,
    transport: httpx2.MockTransport | None = None,
    env: dict[str, str] | None = None,
) -> Any:
    obj = {"transport": transport} if transport is not None else None
    return runner.invoke(app, args, obj=obj, env=env)


def test_cli_zero_side_effect_import_and_help(tmp_path: Path) -> None:
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
            "from tehran_stocks.cli import app, main; assert app.info.name == 'tse'",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout == ""
    assert proc.stderr == ""
    assert not (tmp_path / ".tse").exists()
    assert list(tmp_path.iterdir()) == []

    no_args = runner.invoke(app, [])
    assert no_args.exit_code in (0, 2)
    assert "Usage:" in no_args.output
    for cmd_name in ("search", "quote", "history", "screen", "db", "mcp", "skill"):
        assert cmd_name in no_args.output

    help_res = runner.invoke(app, ["--help"])
    assert help_res.exit_code == 0
    assert "Usage:" in help_res.stdout

    version_res = runner.invoke(app, ["--version"])
    assert version_res.exit_code == 0
    assert "3.0.0" in version_res.stdout


def test_on_demand_search_and_quote_table_json_csv(tmp_path: Path) -> None:
    transport = _make_tsetmc_router()
    env = {"HOME": str(tmp_path)}

    # Table output
    search_tbl = _invoke(["search", "کگل", "--limit", "2"], transport=transport, env=env)
    assert search_tbl.exit_code == 0
    assert "کگل" in search_tbl.stdout
    assert KGL_INS_CODE in search_tbl.stdout

    # --json output
    search_json = _invoke(["search", "کگل", "--limit", "2", "--json"], transport=transport, env=env)
    assert search_json.exit_code == 0
    parsed_search = json.loads(search_json.stdout)
    assert len(parsed_search) == 2
    assert parsed_search[0]["symbol"] == "کگل"
    assert parsed_search[0]["ins_code"] == KGL_INS_CODE

    # --format csv output
    search_csv = _invoke(
        ["search", "کگل", "--limit", "2", "--format", "csv"],
        transport=transport,
        env=env,
    )
    assert search_csv.exit_code == 0
    csv_rows = list(csv.DictReader(io.StringIO(search_csv.stdout)))
    assert len(csv_rows) == 2
    assert csv_rows[0]["symbol"] == "کگل"
    assert csv_rows[0]["ins_code"] == KGL_INS_CODE

    # Quote across table, --format json, and --format csv
    quote_tbl = _invoke(["quote", "کگل"], transport=transport, env=env)
    assert quote_tbl.exit_code == 0
    assert "4,120" in quote_tbl.stdout

    quote_json = _invoke(["quote", "کگل", "--format", "json"], transport=transport, env=env)
    assert quote_json.exit_code == 0
    q_data = json.loads(quote_json.stdout)
    assert q_data["ins_code"] == KGL_INS_CODE
    assert q_data["last"] == pytest.approx(4120.0)
    assert q_data["close"] == pytest.approx(4110.0)
    assert q_data["yesterday"] == pytest.approx(4000.0)
    assert q_data["change"] == pytest.approx(120.0)
    assert q_data["change_pct"] == pytest.approx(3.0)
    assert q_data["state_title"] == "مجاز"
    assert q_data["jdate"] == "1405-09-02"

    quote_csv = _invoke(["quote", "کگل", "--format", "csv"], transport=transport, env=env)
    assert quote_csv.exit_code == 0
    q_csv_rows = list(csv.DictReader(io.StringIO(quote_csv.stdout)))
    assert len(q_csv_rows) == 1
    assert q_csv_rows[0]["ins_code"] == KGL_INS_CODE

    # On-demand commands never create any local database or config files
    assert list(tmp_path.iterdir()) == []


def test_history_client_type_and_orderbook_outputs() -> None:
    adj_payload = {
        "priceAdjust": [
            {
                "insCode": KGL_INS_CODE,
                "dEven": 20261115,
                "pClosing": 2000.0,
                "pClosingNotAdjusted": 4000.0,
                "corporateTypeCode": 1,
            }
        ]
    }
    transport = _make_tsetmc_router(
        extra_routes={
            f"/api/ClosingPrice/GetPriceAdjustList/{KGL_INS_CODE}": adj_payload,
        }
    )

    # History raw vs adjusted
    hist_raw = _invoke(["history", "کگل", "--days", "0", "--json"], transport=transport)
    assert hist_raw.exit_code == 0
    raw_bars = json.loads(hist_raw.stdout)
    assert len(raw_bars) == 15
    assert raw_bars[0]["date"] == "2026-11-02"
    assert "jdate" in raw_bars[0]

    hist_adj = _invoke(
        ["history", "کگل", "--days", "0", "--adjusted", "--json"],
        transport=transport,
    )
    assert hist_adj.exit_code == 0
    adj_bars = json.loads(hist_adj.stdout)
    assert len(adj_bars) == 15
    assert adj_bars[0]["close"] == pytest.approx(raw_bars[0]["close"] * 0.5)
    assert adj_bars[-1]["close"] == pytest.approx(raw_bars[-1]["close"])

    # History CSV filtered by date range
    hist_csv = _invoke(
        [
            "history",
            "کگل",
            "--start",
            "2026-11-17",
            "--end",
            "2026-11-21",
            "--format",
            "csv",
        ],
        transport=transport,
    )
    assert hist_csv.exit_code == 0
    hist_rows = list(csv.DictReader(io.StringIO(hist_csv.stdout)))
    assert [r["date"] for r in hist_rows] == ["2026-11-17", "2026-11-18", "2026-11-21"]

    # Client type live and history
    ct_live = _invoke(["client-type", "کگل", "--json"], transport=transport)
    assert ct_live.exit_code == 0
    ct_data = json.loads(ct_live.stdout)
    assert ct_data["buy_i_volume"] == 168040481
    assert ct_data["net_i_volume"] == 168040481 - 179544124
    assert ct_data["volume_buyer_power"] > 0

    ct_hist = _invoke(
        ["client-type", "کگل", "--history", "--days", "5", "--format", "csv"],
        transport=transport,
    )
    assert ct_hist.exit_code == 0
    ct_rows = list(csv.DictReader(io.StringIO(ct_hist.stdout)))
    assert len(ct_rows) == 5
    assert float(ct_rows[-1]["buyer_power"]) > 0

    # Order book JSON & table
    ob_json = _invoke(["orderbook", "کگل", "--thresholds", "--json"], transport=transport)
    assert ob_json.exit_code == 0
    ob_data = json.loads(ob_json.stdout)
    assert len(ob_data["levels"]) == 5
    assert ob_data["spread"] == pytest.approx(30.0)
    assert ob_data["price_max_allowed"] == pytest.approx(4120.0)
    assert ob_data["is_buy_queue"] is False

    ob_tbl = _invoke(["orderbook", "کگل"], transport=transport)
    assert ob_tbl.exit_code == 0
    assert "4,120" in ob_tbl.stdout
    assert "Spread: 30" in ob_tbl.stdout


def test_info_disclosures_and_market_commands() -> None:
    transport = _make_tsetmc_router()

    info_res = _invoke(["info", "کگل", "--stats", "--identity", "--json"], transport=transport)
    assert info_res.exit_code == 0
    info_data = json.loads(info_res.stdout)
    assert info_data["info"]["eps"] == pytest.approx(275.0)
    assert info_data["identity"]["sub_sector_name"] == "استخراج آهن"
    assert len(info_data["statistics"]) == 20

    etf_res = _invoke(["info", "بمان", "--etf", "--json"], transport=transport)
    assert etf_res.exit_code == 0
    etf_data = json.loads(etf_res.stdout)
    assert etf_data["redemption_nav"] == pytest.approx(23412.0)

    sh_res = _invoke(["shareholders", "کگل", "--json"], transport=transport)
    assert sh_res.exit_code == 0
    sh_data = json.loads(sh_res.stdout)
    assert len(sh_data) == 12
    assert sh_data[0]["percent"] == pytest.approx(33.952)

    div_res = _invoke(
        ["dividends", "کگل", "--share-changes", "--limit", "5", "--json"],
        transport=transport,
    )
    assert div_res.exit_code == 0
    div_data = json.loads(div_res.stdout)
    assert len(div_data["adjustments"]) == 5
    assert len(div_data["share_changes"]) == 5

    mkt_res = _invoke(["market", "--json"], transport=transport)
    assert mkt_res.exit_code == 0
    mkt_data = json.loads(mkt_res.stdout)
    assert mkt_data["index_value"] == pytest.approx(8389814.07)
    assert mkt_data["market_state"] == "بسته"

    sec_res = _invoke(["sectors", "--json"], transport=transport)
    assert sec_res.exit_code == 0
    sec_data = json.loads(sec_res.stdout)
    assert any(s["code"] == "13" and s["name"] == "استخراج کانه های فلزی" for s in sec_data)

    idx_res = _invoke(["indices", "--limit", "5", "--json"], transport=transport)
    assert idx_res.exit_code == 0
    idx_data = json.loads(idx_res.stdout)
    assert len(idx_data) == 5
    assert idx_data[0]["change_pct"] == pytest.approx(1.6846)

    idx_hist = _invoke(
        ["indices", "--history", "TEDPIX", "--limit", "5", "--json"],
        transport=transport,
    )
    assert idx_hist.exit_code == 0
    idx_hist_data = json.loads(idx_hist.stdout)
    assert len(idx_hist_data) == 5
    assert idx_hist_data[-1]["date"] == "2026-11-22"

    codal_res = _invoke(["codal", "کگل", "--limit", "3", "--json"], transport=transport)
    assert codal_res.exit_code == 0
    codal_data = json.loads(codal_res.stdout)
    assert len(codal_data) == 3
    assert codal_data[0]["tracing_no"] == 1633100

    msg_res = _invoke(["messages", "کگل", "--limit", "3", "--format", "csv"], transport=transport)
    assert msg_res.exit_code == 0
    msg_rows = list(csv.DictReader(io.StringIO(msg_res.stdout)))
    assert len(msg_rows) == 3
    assert msg_rows[0]["msg_id"] == "264802"


def test_screen_sorting_and_sector_filtering() -> None:
    transport = _make_tsetmc_router()

    # Sort by value (default)
    by_value = _invoke(["screen", "--sort", "value", "--limit", "3", "--json"], transport=transport)
    assert by_value.exit_code == 0
    value_rows = json.loads(by_value.stdout)
    assert len(value_rows) == 3
    assert value_rows[0]["symbol"] == "افران"
    assert value_rows[0]["value"] >= value_rows[1]["value"] >= value_rows[2]["value"]

    # Sort by volume in CSV format
    by_volume = _invoke(
        ["screen", "--sort", "volume", "--limit", "3", "--format", "csv"],
        transport=transport,
    )
    assert by_volume.exit_code == 0
    vol_rows = list(csv.DictReader(io.StringIO(by_volume.stdout)))
    assert len(vol_rows) == 3
    assert vol_rows[0]["symbol"] == "افران"

    # Sort by change %
    by_change = _invoke(["screen", "--sort", "change", "--limit", "3", "--json"], transport=transport)
    assert by_change.exit_code == 0
    chg_rows = json.loads(by_change.stdout)
    assert chg_rows[0]["change_pct"] >= chg_rows[1]["change_pct"] >= chg_rows[2]["change_pct"]
    assert chg_rows[0]["symbol"] == "ضهرم9025"

    # Sort by real money flow (joins GetClientTypeAll + GetMarketWatch)
    by_flow = _invoke(
        ["screen", "--sort", "money_flow", "--limit", "5", "--json"],
        transport=transport,
    )
    assert by_flow.exit_code == 0
    flow_rows = json.loads(by_flow.stdout)
    assert len(flow_rows) == 5
    assert flow_rows[0]["symbol"] == "مبین"
    assert flow_rows[0]["real_money_flow"] > 0
    assert flow_rows[0]["real_money_flow"] >= flow_rows[1]["real_money_flow"]

    # Sort by buyer power
    by_power = _invoke(
        ["screen", "--sort", "buyer_power", "--limit", "5", "--json"],
        transport=transport,
    )
    assert by_power.exit_code == 0
    power_rows = json.loads(by_power.stdout)
    assert power_rows[0]["buyer_power"] >= power_rows[1]["buyer_power"]
    assert power_rows[0]["symbol"] == "دیران"

    # Filter by numeric sector code
    sec_code = _invoke(["screen", "--sector", "68", "--json"], transport=transport)
    assert sec_code.exit_code == 0
    sec_code_rows = json.loads(sec_code.stdout)
    assert len(sec_code_rows) == 8
    assert all(r["sector_code"] == "68" for r in sec_code_rows)

    # Filter by Persian sector name substring
    sec_name = _invoke(["screen", "--sector", "دارو", "--json"], transport=transport)
    assert sec_name.exit_code == 0
    sec_name_rows = json.loads(sec_name.stdout)
    assert [r["symbol"] for r in sec_name_rows] == ["دیران"]

    # Rich table output for screen
    screen_tbl = _invoke(["screen", "--sort", "money_flow", "--limit", "2"], transport=transport)
    assert screen_tbl.exit_code == 0
    assert "مبین" in screen_tbl.stdout


def test_db_init_sync_status_query_and_readonly_enforcement(tmp_path: Path) -> None:
    transport = _make_tsetmc_router()
    db_path = tmp_path / "tse.sqlite"

    # Status on nonexistent file (including sqlite+pysqlite:///) fails cleanly without creating DB
    missing_res = _invoke(["db", "status", "--db", str(db_path)], transport=transport)
    assert missing_res.exit_code == 6
    assert "StorageError:" in missing_res.stderr
    assert not db_path.exists()

    missing_sqla_sqlite = tmp_path / "missing_sqla.sqlite"
    missing_sqla_res = _invoke(
        ["db", "status", "--db", f"sqlite+pysqlite:///{missing_sqla_sqlite}"],
        transport=transport,
    )
    assert missing_sqla_res.exit_code == 6
    assert "StorageError:" in missing_sqla_res.stderr
    assert not missing_sqla_sqlite.exists()

    # Init
    init_res = _invoke(["db", "init", "--db", str(db_path), "--json"])
    assert init_res.exit_code == 0
    init_data = json.loads(init_res.stdout)
    assert init_data["status"] == "initialized"
    assert init_data["schema_version"] == 1
    assert db_path.exists()

    # Sync single symbol with client-type flow
    sync_res = _invoke(
        ["db", "sync", "--db", str(db_path), "--symbols", "کگل", "--client-type", "--json"],
        transport=transport,
    )
    assert sync_res.exit_code == 0
    sync_data = json.loads(sync_res.stdout)
    assert sync_data["instruments"] == 12
    assert sync_data["sectors"] > 0
    assert sync_data["prices"] == 15
    assert sync_data["adjustments"] == 15
    assert sync_data["client_types"] == 15
    assert "Syncing" in sync_res.stderr

    # Second incremental sync writes 0 new rows
    sync_again = _invoke(
        ["db", "sync", "--db", str(db_path), "--symbols", "کگل", "--client-type", "--json"],
        transport=transport,
    )
    assert sync_again.exit_code == 0
    again_data = json.loads(sync_again.stdout)
    assert again_data["prices"] == 0
    assert again_data["client_types"] == 0

    # Status (JSON and table)
    status_res = _invoke(["db", "status", "--db", str(db_path), "--json"])
    assert status_res.exit_code == 0
    status_data = json.loads(status_res.stdout)
    assert status_data["daily_prices"] == 15
    assert status_data["client_types"] == 15
    assert status_data["instruments"] == 12

    status_tbl = _invoke(["db", "status", "--db", str(db_path)])
    assert status_tbl.exit_code == 0
    assert "daily_prices" in status_tbl.stdout

    # Reject conflicting sync flags cleanly
    conflict_res = _invoke(
        ["db", "sync", "--db", str(db_path), "--all", "--symbols", "کگل"],
        transport=transport,
    )
    assert conflict_res.exit_code == 2
    assert "ValueError:" in conflict_res.stderr

    conflict_sym_sec = _invoke(
        ["db", "sync", "--db", str(db_path), "--symbols", "کگل", "--sector", "13"],
        transport=transport,
    )
    assert conflict_sym_sec.exit_code == 2
    assert "ValueError:" in conflict_sym_sec.stderr

    # Query SELECT in JSON and CSV
    query_json = _invoke(
        [
            "db",
            "query",
            "--db",
            str(db_path),
            "SELECT date, close, volume FROM daily_prices ORDER BY date ASC LIMIT 3",
            "--json",
        ]
    )
    assert query_json.exit_code == 0
    q_rows = json.loads(query_json.stdout)
    assert [r["date"] for r in q_rows] == ["2026-11-02", "2026-11-03", "2026-11-04"]

    query_csv = _invoke(
        [
            "db",
            "query",
            "--db",
            str(db_path),
            "SELECT symbol, sector_code FROM instruments WHERE sector_code = '43'",
            "--format",
            "csv",
        ]
    )
    assert query_csv.exit_code == 0
    q_csv = list(csv.DictReader(io.StringIO(query_csv.stdout)))
    assert q_csv == [{"symbol": "دیران", "sector_code": "43"}]

    # Mutating / multi-statement SQL must be rejected cleanly with non-zero exit
    for bad_sql in (
        "DELETE FROM daily_prices",
        "DROP TABLE instruments",
        "INSERT INTO sectors (code, name) VALUES ('99', 'test')",
        "UPDATE instruments SET symbol = 'X'",
        "SELECT 1; DROP TABLE daily_prices",
        "PRAGMA journal_mode = DELETE",
    ):
        bad_res = _invoke(["db", "query", "--db", str(db_path), bad_sql])
        assert bad_res.exit_code == 6
        assert bad_res.stdout == ""
        assert "StorageError:" in bad_res.stderr

    # Verify DB remained untouched after rejected mutating queries
    after_status = json.loads(_invoke(["db", "status", "--db", str(db_path), "--json"]).stdout)
    assert after_status["daily_prices"] == 15
    assert after_status["instruments"] == 12


def test_error_exit_codes_global_options_and_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    def error_handler(request: httpx2.Request) -> httpx2.Response:
        path = unquote(request.url.path)
        if path.startswith("/api/Instrument/GetInstrumentSearch/"):
            return httpx2.Response(200, json={"instrumentSearch": []})
        if path == "/api/ClosingPrice/GetClosingPriceInfo/429429":
            return httpx2.Response(429, headers={"Retry-After": "0"})
        if path == "/api/ClosingPrice/GetClosingPriceInfo/500500":
            return httpx2.Response(500, json={"error": "server failure"})
        return httpx2.Response(200, json=_load_fixture("quote.json"))

    err_transport = httpx2.MockTransport(error_handler)
    monkeypatch.setattr(cli_mod, "_TRANSPORT_OVERRIDE", err_transport)

    not_found = runner.invoke(app, ["quote", "ناموجود"])
    assert not_found.exit_code == 3
    assert not_found.stdout == ""
    assert "InstrumentNotFoundError:" in not_found.stderr

    # Patch max_retries=0 via create_client wrapper to avoid backoff waits on 429/500
    captured_calls: list[dict[str, Any]] = []
    from tehran_stocks.client.base import TSETMCClient

    def fast_client_factory(
        *,
        timeout: float = 15.0,
        proxy: str | None = None,
        transport: httpx2.BaseTransport | None = None,
    ) -> TSETMCClient:
        captured_calls.append({"timeout": timeout, "proxy": proxy})
        return TSETMCClient(
            timeout=timeout,
            proxy=None,
            max_retries=0,
            retry_backoff=0.0,
            transport=transport if transport is not None else err_transport,
        )

    monkeypatch.setattr(cli_mod, "create_client", fast_client_factory)

    rate_limited = runner.invoke(app, ["quote", "429429"])
    assert rate_limited.exit_code == 4
    assert rate_limited.stdout == ""
    assert "RateLimitError:" in rate_limited.stderr

    upstream_err = runner.invoke(app, ["quote", "500500"])
    assert upstream_err.exit_code == 5
    assert upstream_err.stdout == ""
    assert "TSETMCError:" in upstream_err.stderr

    # Verify global --timeout validation and --timeout / --proxy forwarding
    bad_timeout = runner.invoke(app, ["--timeout", "0", "quote", "35700344742885862"])
    assert bad_timeout.exit_code == 2
    assert "ValueError:" in bad_timeout.stderr

    ok_res = runner.invoke(
        app,
        ["--timeout", "25", "--proxy", "http://127.0.0.1:8888", "quote", "35700344742885862", "--json"],
    )
    assert ok_res.exit_code == 0
    assert captured_calls[-1] == {"timeout": 25.0, "proxy": "http://127.0.0.1:8888"}

    # Verify PR 4 (mcp) hook prefers run_server when present and falls back to create_server
    import tehran_stocks

    run_server_calls: list[dict[str, Any]] = []
    fake_mcp_run_mod = types.ModuleType("tehran_stocks.mcp_server")
    fake_mcp_run_mod.run_server = lambda **kwargs: run_server_calls.append(kwargs)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tehran_stocks.mcp_server", fake_mcp_run_mod)
    monkeypatch.setattr(tehran_stocks, "mcp_server", fake_mcp_run_mod, raising=False)

    mcp_run_res = runner.invoke(
        app,
        ["mcp", "--db", "/tmp/test.sqlite", "--transport", "streamable-http", "--port", "9001"],
    )
    assert mcp_run_res.exit_code == 0
    assert run_server_calls == [
        {
            "db_path": "/tmp/test.sqlite",
            "transport": "streamable-http",
            "timeout": 15.0,
            "proxy": None,
            "host": "127.0.0.1",
            "port": 9001,
        }
    ]

    # Verify fallback to create_server when run_server is absent
    mcp_calls: list[dict[str, Any]] = []

    class FakeServer:
        def run(self, **kwargs: Any) -> None:
            mcp_calls.append({"run_kwargs": kwargs})

    fake_mcp_mod = types.ModuleType("tehran_stocks.mcp_server")

    def fake_create_server(**kwargs: Any) -> FakeServer:
        mcp_calls.append({"create_kwargs": kwargs})
        return FakeServer()

    fake_mcp_mod.create_server = fake_create_server  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tehran_stocks.mcp_server", fake_mcp_mod)
    monkeypatch.setattr(tehran_stocks, "mcp_server", fake_mcp_mod, raising=False)

    mcp_res = runner.invoke(app, ["mcp", "--db", "/tmp/test.sqlite", "--transport", "stdio"])
    assert mcp_res.exit_code == 0
    assert mcp_calls == [
        {
            "create_kwargs": {
                "db_path": "/tmp/test.sqlite",
                "timeout": 15.0,
                "proxy": None,
                "transport": "stdio",
            }
        },
        {"run_kwargs": {"transport": "stdio"}},
    ]

    # Verify PR 5 (skill) sub-app hook help works
    skill_help = runner.invoke(app, ["skill", "--help"])
    assert skill_help.exit_code == 0
    assert "skill" in skill_help.stdout.lower()


SECRET_DB_URL = "postgresql://alice:s3cr3t_pw@localhost:5432/tse?sslmode=require"
SAFE_DB_URL = "postgresql://localhost:5432/tse"


def _assert_no_db_secrets(result: Any) -> None:
    combined = result.stdout + result.stderr
    assert "s3cr3t_pw" not in combined
    assert "alice" not in combined
    assert "sslmode" not in combined


class _FakeCliStore:
    def __init__(self, target: str) -> None:
        self.target = target
        self.closed = False

    def init_schema(self) -> None:
        return None

    def stats(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "sectors": 0,
            "instruments": 0,
            "daily_prices": 0,
            "client_types": 0,
            "price_adjustments": 0,
            "share_changes": 0,
            "sync_meta": 0,
        }

    def close(self) -> None:
        self.closed = True


def _patch_fake_storage(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sync_errors: dict[str, str] | None = None,
    open_error: str | None = None,
) -> list[str]:
    import tehran_stocks.storage as storage_mod
    from tehran_stocks.exceptions import StorageError
    from tehran_stocks.storage import SyncResult

    opened: list[str] = []

    def fake_open_store(
        target: Any,
        *,
        backend: str | None = None,
        init_schema: bool = True,
        **kwargs: Any,
    ) -> _FakeCliStore:
        opened.append(str(target))
        if open_error is not None:
            raise StorageError(open_error.format(target=target))
        return _FakeCliStore(str(target))

    class FakeSyncService:
        def __init__(self, store: Any, **kwargs: Any) -> None:
            self.store = store

        def sync_all(self, **kwargs: Any) -> SyncResult:
            errors = dict(sync_errors or {})
            return SyncResult(
                sectors=2,
                instruments=12,
                prices=15,
                synced_symbols=1,
                skipped_symbols=len(errors),
                errors=errors,
            )

    monkeypatch.setattr(storage_mod, "open_store", fake_open_store)
    monkeypatch.setattr(storage_mod, "SyncService", FakeSyncService)
    return opened


def test_sanitize_db_target_strips_credentials_and_query() -> None:
    assert cli_mod._sanitize_db_target(SECRET_DB_URL) == SAFE_DB_URL
    assert (
        cli_mod._sanitize_db_target(
            "postgresql+psycopg://user:pass@host:5432/db?sslmode=require"
        )
        == "postgresql+psycopg://host:5432/db"
    )
    assert cli_mod._sanitize_db_target("mysql+pymysql://u:p%40ss@db.example.com/tse") == (
        "mysql+pymysql://db.example.com/tse"
    )
    assert cli_mod._sanitize_db_target("./tse.sqlite") == "./tse.sqlite"
    assert cli_mod._sanitize_db_target("/data/tse.sqlite") == "/data/tse.sqlite"
    assert cli_mod._sanitize_db_target(":memory:") == ":memory:"
    assert cli_mod._sanitize_db_target("sqlite:////data/tse.sqlite") == "sqlite:////data/tse.sqlite"
    assert cli_mod._sanitize_db_target("duckdb:///./tse.duckdb") == "duckdb:///./tse.duckdb"

    redacted = cli_mod._redact_db_message(
        f'connect to {SECRET_DB_URL} failed: password authentication failed for user "alice"',
        SECRET_DB_URL,
    )
    assert SAFE_DB_URL in redacted
    assert "alice" not in redacted
    assert "s3cr3t_pw" not in redacted


def test_db_commands_never_leak_database_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    opened = _patch_fake_storage(monkeypatch)

    commands: list[list[str]] = [
        ["db", "init", "--db", SECRET_DB_URL],
        ["db", "sync", "--db", SECRET_DB_URL, "--symbols", "کگل"],
        ["db", "status", "--db", SECRET_DB_URL],
    ]
    for base_args in commands:
        json_res = _invoke([*base_args, "--json"])
        assert json_res.exit_code == 0, json_res.stderr
        _assert_no_db_secrets(json_res)
        assert json.loads(json_res.stdout)["db"] == SAFE_DB_URL

        table_res = _invoke(base_args)
        assert table_res.exit_code == 0, table_res.stderr
        _assert_no_db_secrets(table_res)

        csv_res = _invoke([*base_args, "--format", "csv"])
        assert csv_res.exit_code == 0, csv_res.stderr
        _assert_no_db_secrets(csv_res)

    # TEHRAN_STOCKS_DB env var path is sanitized as well.
    env_res = _invoke(["db", "status", "--json"], env={"TEHRAN_STOCKS_DB": SECRET_DB_URL})
    assert env_res.exit_code == 0
    _assert_no_db_secrets(env_res)
    assert json.loads(env_res.stdout)["db"] == SAFE_DB_URL

    # The real (credential-bearing) URL is still what the store connects with.
    assert opened and all(target == SECRET_DB_URL for target in opened)


def test_db_command_errors_never_leak_database_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_fake_storage(
        monkeypatch,
        open_error=(
            "SQLAlchemy storage error: (psycopg.OperationalError) connection to {target} "
            'failed: FATAL: password authentication failed for user "alice" (s3cr3t_pw)'
        ),
    )

    for args in (
        ["db", "init", "--db", SECRET_DB_URL],
        ["db", "sync", "--db", SECRET_DB_URL, "--symbols", "کگل"],
        ["db", "status", "--db", SECRET_DB_URL],
        ["db", "query", "--db", SECRET_DB_URL, "SELECT 1"],
    ):
        res = _invoke(args)
        assert res.exit_code == 6
        assert res.stdout == ""
        assert "StorageError:" in res.stderr
        assert "password authentication failed" in res.stderr
        _assert_no_db_secrets(res)


def test_db_sync_partial_failure_emits_summary_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sync_errors = {"ناموجود": "InstrumentNotFoundError: Instrument not found: ناموجود"}
    _patch_fake_storage(monkeypatch, sync_errors=sync_errors)
    db = str(tmp_path / "partial.sqlite")

    json_res = _invoke(["db", "sync", "--db", db, "--symbols", "کگل,ناموجود", "--json"])
    assert json_res.exit_code == 1
    summary = json.loads(json_res.stdout)
    assert summary["prices"] == 15
    assert summary["synced_symbols"] == 1
    assert summary["skipped_symbols"] == 1
    assert summary["errors"] == sync_errors
    assert summary["db"] == db
    assert "Sync warning" in json_res.stderr
    assert "ناموجود" in json_res.stderr

    table_res = _invoke(["db", "sync", "--db", db, "--symbols", "کگل,ناموجود"])
    assert table_res.exit_code == 1
    assert "Completed with Errors" in table_res.stdout
    assert "prices" in table_res.stdout
    assert "Sync warning" in table_res.stderr

    csv_res = _invoke(["db", "sync", "--db", db, "--symbols", "کگل,ناموجود", "--format", "csv"])
    assert csv_res.exit_code == 1
    csv_rows = list(csv.DictReader(io.StringIO(csv_res.stdout)))
    assert csv_rows[0]["prices"] == "15"

    # A clean sync keeps exit code 0 and the normal title.
    _patch_fake_storage(monkeypatch, sync_errors={})
    ok_res = _invoke(["db", "sync", "--db", db, "--symbols", "کگل"])
    assert ok_res.exit_code == 0
    assert "Database Sync Complete" in ok_res.stdout
    assert "Completed with Errors" not in ok_res.stdout
