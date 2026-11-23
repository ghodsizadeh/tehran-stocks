"""Tests for the official mcp>=2.0 MCPServer tools, resources, DB guards, and stdout purity."""

from __future__ import annotations

import importlib.util
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any
from urllib.parse import unquote

import httpx2
from mcp import Client as MCPTestClient
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ToolError
from mcp.shared.exceptions import MCPError
import pytest

from tehran_stocks.exceptions import StorageError
from tehran_stocks.mcp_server import (
    configure_stderr_logging,
    create_server,
    main,
    resolve_server_config,
    run_server,
)
from tehran_stocks.mcp_server.tools import _local_sqlite_file_path

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
KGL_INS_CODE = "35700344742885862"
ETF_INS_CODE = "52551569846042389"
TEDPIX_INS_CODE = "32097828799138957"

EXPECTED_ON_DEMAND_TOOLS = {
    "search_instruments",
    "get_stock_snapshot",
    "get_price_history",
    "get_client_type_flow",
    "get_order_book",
    "get_fundamentals_and_events",
    "get_market_overview",
    "get_indices",
    "screen_market",
    "get_disclosures",
}
EXPECTED_DB_TOOLS = {"sync_local_db", "query_local_db"}


def _load_fixture(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _make_tsetmc_transport(
    calls: list[str] | None = None,
    *,
    extra_routes: dict[str, Any] | None = None,
) -> httpx2.MockTransport:
    """Build an httpx2.MockTransport serving recorded TSETMC JSON fixtures."""
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
    }

    trade_top_payload: dict[str, Any] = {
        "tradeTop": [
            {
                "instrument": {
                    "insCode": KGL_INS_CODE,
                    "lVal18AFC": "كگل",
                    "lVal30": "معدني و صنعتي گل گهر",
                    "cIsin": "IRO1GOLG0005",
                },
                "pDrCotVal": 4120.0,
                "pClosing": 4110.0,
                "priceYesterday": 4000.0,
                "qTotTran5J": 441108505,
                "qTotCap": 1814088254160,
                "zTotTran": 4608,
            }
        ]
    }

    routes: dict[str, Any] = {
        f"/api/Instrument/GetInstrumentInfo/{KGL_INS_CODE}": fixtures["info"],
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
        f"/api/Index/GetInstEffect/{TEDPIX_INS_CODE}/1/10": {
            "instEffect": [
                {
                    "instrument": {
                        "insCode": KGL_INS_CODE,
                        "lVal18AFC": "كگل",
                        "lVal30": "معدني و صنعتي گل گهر",
                    },
                    "pClosing": 4110.0,
                    "priceChange": 110.0,
                    "instEffectValue": 4250.5,
                }
            ]
        },
        "/api/ClosingPrice/GetTradeTop/1/1/5": trade_top_payload,
        "/api/ClosingPrice/GetTradeTop/1/1/10": trade_top_payload,
        f"/api/Shareholder/GetInstrumentShareHolderLast/{KGL_INS_CODE}": fixtures["shareholders"],
        f"/api/Codal/GetPreparedDataByInsCode/10/{KGL_INS_CODE}": fixtures["codal"],
        f"/api/Msg/GetMsgByInsCode/{KGL_INS_CODE}": fixtures["messages"],
        f"/api/Fund/GetETFByInsCode/{ETF_INS_CODE}": fixtures["etf"],
        f"/api/Instrument/GetInstrumentInfo/{ETF_INS_CODE}": {
            "instrumentInfo": {
                "insCode": ETF_INS_CODE,
                "lVal18AFC": "بمان",
                "lVal30": "صندوق س.بازده مانا-د",
                "flow": 2,
                "flowTitle": "بازار فرابورس",
                "cIsin": "IRT3BMNF0001",
                "zTitad": 1400000000,
                "sector": {"cSecVal": "68 ", "lSecVal": "صندوق سرمايه گذاري قابل معامله"},
                "staticThreshold": {"psGelStaMax": 24206.0, "psGelStaMin": 22796.0},
            }
        },
        f"/api/Instrument/GetInstrumentIdentity/{ETF_INS_CODE}": {
            "instrumentIdentity": {
                "insCode": ETF_INS_CODE,
                "lVal18AFC": "بمان",
                "lVal30": "صندوق س.بازده مانا-د",
                "flow": 2,
                "flowTitle": "بازار فرابورس",
            }
        },
    }
    if extra_routes:
        routes.update(extra_routes)

    def handler(request: httpx2.Request) -> httpx2.Response:
        path = unquote(request.url.path)
        if calls is not None:
            calls.append(path)

        if path in routes:
            target = routes[path]
            return target(request) if callable(target) else httpx2.Response(200, json=target)

        if path.startswith("/api/Instrument/GetInstrumentSearch/"):
            query = path.removeprefix("/api/Instrument/GetInstrumentSearch/")
            if query in ("ناموجود", "NOT_FOUND"):
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

        daily_prefix = f"/api/ClosingPrice/GetClosingPriceDailyList/{KGL_INS_CODE}/"
        if path.startswith(daily_prefix):
            days_str = path.removeprefix(daily_prefix)
            days = int(days_str) if days_str.isdigit() else 0
            all_rows = fixtures["daily_history"]["closingPriceDaily"]
            selected = all_rows[:days] if days > 0 else all_rows
            return httpx2.Response(200, json={"closingPriceDaily": selected})

        return httpx2.Response(404, json={"error": f"Unhandled path: {path}"})

    return httpx2.MockTransport(handler)


def test_import_and_create_server_stdout_purity_and_zero_side_effects(tmp_path: Path) -> None:
    src_dir = Path(__file__).resolve().parents[2] / "src"
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "PYTHONPATH": str(src_dir),
    }
    env.pop("TEHRAN_STOCKS_DB", None)
    env.pop("TEHRAN_STOCKS_TIMEOUT", None)
    env.pop("TEHRAN_STOCKS_PROXY", None)

    script = (
        "from tehran_stocks.mcp_server import create_server; "
        "s1 = create_server(); "
        f"s2 = create_server(db_path={str(tmp_path / 'never_created.sqlite')!r}); "
        "assert s1.name == 'tehran-stocks' and s2.name == 'tehran-stocks'"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout == ""
    assert list(tmp_path.iterdir()) == []


def test_stderr_logging_never_writes_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_stderr_logging("INFO")
    logger = logging.getLogger("tehran_stocks.mcp_server.test")
    logger.info("mcp stderr probe message")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "mcp stderr probe message" in captured.err


def test_config_resolution_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEHRAN_STOCKS_DB", raising=False)
    monkeypatch.delenv("TEHRAN_STOCKS_TIMEOUT", raising=False)
    monkeypatch.delenv("TEHRAN_STOCKS_PROXY", raising=False)

    cfg = resolve_server_config()
    assert cfg.db_path is None
    assert cfg.timeout == 20.0
    assert cfg.proxy is None
    assert cfg.transport is None

    monkeypatch.setenv("TEHRAN_STOCKS_DB", "/tmp/env_tse.sqlite")
    monkeypatch.setenv("TEHRAN_STOCKS_TIMEOUT", "35.5")
    monkeypatch.setenv("TEHRAN_STOCKS_PROXY", "http://127.0.0.1:8080")
    env_cfg = resolve_server_config()
    assert env_cfg.db_path == "/tmp/env_tse.sqlite"
    assert env_cfg.timeout == 35.5
    assert env_cfg.proxy == "http://127.0.0.1:8080"

    with pytest.raises(ValueError, match="timeout"):
        create_server(timeout=0)
    with pytest.raises(ValueError, match="Unsupported transport"):
        create_server(transport="invalid-transport")


@pytest.mark.asyncio
async def test_registered_tools_resources_and_schemas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEHRAN_STOCKS_DB", raising=False)

    server = create_server()
    assert isinstance(server, MCPServer)

    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == EXPECTED_ON_DEMAND_TOOLS
    assert tool_names.isdisjoint(EXPECTED_DB_TOOLS)

    for tool in tools:
        assert tool.description
        assert tool.input_schema.get("type") == "object"
        assert tool.output_schema is not None
        assert tool.output_schema.get("type") == "object"
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True

    resources = await server.list_resources()
    resource_uris = {str(r.uri) for r in resources}
    assert resource_uris == {"tsetmc://market/overview", "tsetmc://market/sectors"}
    assert all(r.mime_type == "application/json" for r in resources)

    templates = await server.list_resource_templates()
    assert {t.uri_template for t in templates} == {"tsetmc://instrument/{symbol}"}

    # Opt-in DB tools appear when db_path or TEHRAN_STOCKS_DB is set.
    db_server = create_server(db_path=":memory:")
    db_tools = {t.name: t for t in await db_server.list_tools()}
    assert set(db_tools) == EXPECTED_ON_DEMAND_TOOLS | EXPECTED_DB_TOOLS
    assert db_tools["query_local_db"].annotations is not None
    assert db_tools["query_local_db"].annotations.read_only_hint is True
    assert db_tools["sync_local_db"].annotations is not None
    assert db_tools["sync_local_db"].annotations.read_only_hint is False

    monkeypatch.setenv("TEHRAN_STOCKS_DB", ":memory:")
    env_db_server = create_server()
    assert set(t.name for t in await env_db_server.list_tools()) == (
        EXPECTED_ON_DEMAND_TOOLS | EXPECTED_DB_TOOLS
    )


@pytest.mark.asyncio
async def test_all_on_demand_tools_and_resources_via_mcp_client() -> None:
    calls: list[str] = []
    transport = _make_tsetmc_transport(calls=calls)
    server = create_server(client_transport=transport)

    async with MCPTestClient(server) as mcp_client:
        # 1. search_instruments
        search_res = await mcp_client.call_tool("search_instruments", {"query": "کگل", "limit": 3})
        assert not search_res.is_error
        search_data = search_res.structured_content
        assert search_data["query"] == "کگل"
        assert search_data["count"] == 3
        assert search_data["instruments"][0]["ins_code"] == KGL_INS_CODE
        assert search_data["instruments"][0]["symbol"] == "کگل"

        # 2. get_stock_snapshot
        snap_res = await mcp_client.call_tool("get_stock_snapshot", {"symbol": "كگل"})
        assert not snap_res.is_error
        snap = snap_res.structured_content
        assert snap["ins_code"] == KGL_INS_CODE
        assert snap["symbol"] == "کگل"
        assert snap["currency"] == "IRR"
        assert snap["quote"]["last"] == pytest.approx(4120.0)
        assert snap["quote"]["close"] == pytest.approx(4110.0)
        assert snap["valuation"]["eps"] == pytest.approx(275.0)
        assert snap["valuation"]["pe_ratio"] == pytest.approx(round(4110.0 / 275.0, 2))
        assert len(snap["order_book"]["levels"]) == 5
        assert snap["order_book"]["spread"] == pytest.approx(30.0)
        assert snap["client_type"]["buy_i_count"] == 628
        assert snap["client_type"]["volume_buyer_power"] > 0
        # Verify JSON round-trip of text block too
        assert json.loads(snap_res.content[0].text)["ins_code"] == KGL_INS_CODE

        # 3. get_price_history (default days=30, unadjusted days=0, and range defaulting to days=0)
        hist_default = await mcp_client.call_tool("get_price_history", {"symbol": "کگل"})
        assert not hist_default.is_error
        assert f"/api/ClosingPrice/GetClosingPriceDailyList/{KGL_INS_CODE}/30" in calls

        hist_raw = await mcp_client.call_tool(
            "get_price_history",
            {"symbol": "کگل", "days": 0, "adjusted": False},
        )
        assert not hist_raw.is_error
        assert hist_raw.structured_content["count"] == 15
        assert hist_raw.structured_content["bars"][0]["jdate"]

        calls.clear()
        hist_adj = await mcp_client.call_tool(
            "get_price_history",
            {
                "symbol": "کگل",
                "start": "2026-11-02",
                "end": "2026-11-22",
                "adjusted": True,
                "limit": 5,
            },
        )
        assert not hist_adj.is_error
        assert f"/api/ClosingPrice/GetClosingPriceDailyList/{KGL_INS_CODE}/0" in calls
        adj_data = hist_adj.structured_content
        assert adj_data["adjusted"] is True
        assert adj_data["count"] == 5
        assert adj_data["bars"][-1]["date"] == "2026-11-22"
        assert adj_data["summary"]["latest_close"] == pytest.approx(4000.0)

        # 4. get_client_type_flow
        ct_res = await mcp_client.call_tool("get_client_type_flow", {"symbol": "کگل", "days": 5})
        assert not ct_res.is_error
        ct_data = ct_res.structured_content
        assert ct_data["ins_code"] == KGL_INS_CODE
        assert ct_data["history_count"] == 5
        assert ct_data["history"][-1]["real_money_flow"] == 681368933310 - 550052671100
        assert ct_data["history"][-1]["buyer_power"] > 0
        assert ct_data["history"][-1]["jdate"]
        assert ct_data["summary"]["inflow_days"] >= 0

        # 5. get_order_book
        book_res = await mcp_client.call_tool(
            "get_order_book",
            {"symbol": "کگل", "include_thresholds": True},
        )
        assert not book_res.is_error
        book_data = book_res.structured_content
        assert len(book_data["levels"]) == 5
        assert book_data["price_max_allowed"] == pytest.approx(4120.0)
        assert book_data["is_buy_queue"] is False
        assert book_data["is_sell_queue"] is False

        # 6. get_fundamentals_and_events (equity + ETF)
        fund_res = await mcp_client.call_tool(
            "get_fundamentals_and_events",
            {"symbol": "کگل"},
        )
        assert not fund_res.is_error
        fund_data = fund_res.structured_content
        assert fund_data["info"]["eps"] == pytest.approx(275.0)
        assert fund_data["identity"]["sub_sector_name"] == "استخراج آهن"
        assert len(fund_data["statistics"]) == 20
        assert len(fund_data["shareholders"]) == 12
        assert len(fund_data["share_changes"]) == 15
        assert len(fund_data["adjustments"]) == 15

        etf_res = await mcp_client.call_tool(
            "get_fundamentals_and_events",
            {
                "symbol": "بمان",
                "include_statistics": False,
                "include_shareholders": False,
                "include_share_changes": False,
                "include_adjustments": False,
                "include_etf": True,
            },
        )
        assert not etf_res.is_error
        assert etf_res.structured_content["etf"]["redemption_nav"] == pytest.approx(23412.0)

        # 7. get_market_overview
        mkt_res = await mcp_client.call_tool(
            "get_market_overview",
            {"flow": 1, "include_sectors": True, "include_top_trades": True, "top_limit": 5},
        )
        assert not mkt_res.is_error
        mkt_data = mkt_res.structured_content
        assert mkt_data["overview"]["index_value"] == pytest.approx(8389814.07)
        assert mkt_data["sectors_count"] > 0
        assert mkt_data["top_trades_count"] == 1

        # 8. get_indices
        idx_res = await mcp_client.call_tool(
            "get_indices",
            {"flow": 1, "index_code": "TEDPIX", "history_days": 5, "include_effect": True},
        )
        assert not idx_res.is_error
        idx_data = idx_res.structured_content
        assert idx_data["count"] > 0
        assert idx_data["selected_index"]["history_count"] == 5
        assert idx_data["selected_index"]["top_effects"][0]["symbol"] == "کگل"

        # 9. screen_market
        screen_res = await mcp_client.call_tool(
            "screen_market",
            {
                "sector_code": "68",
                "min_value": 100_000_000_000,
                "min_buyer_power": 1.0,
                "sort_by": "buyer_power",
                "limit": 10,
            },
        )
        assert not screen_res.is_error
        screen_data = screen_res.structured_content
        assert screen_data["returned_count"] >= 1
        assert all(item["sector_code"] == "68" for item in screen_data["results"])
        assert all(item["buyer_power"] >= 1.0 for item in screen_data["results"])

        screen_flow_res = await mcp_client.call_tool(
            "screen_market",
            {"sort_by": "real_money_flow", "limit": 5},
        )
        assert not screen_flow_res.is_error
        assert screen_flow_res.structured_content["results"][0]["symbol"] == "مبین"
        assert screen_flow_res.structured_content["results"][0]["real_money_flow"] > 0

        # 10. get_disclosures
        disc_res = await mcp_client.call_tool(
            "get_disclosures",
            {"symbol": "کگل", "codal_limit": 10, "messages_limit": 3},
        )
        assert not disc_res.is_error
        disc_data = disc_res.structured_content
        assert disc_data["codal_count"] == 5
        assert disc_data["messages_count"] == 3
        assert disc_data["codal"][0]["tracing_no"] == 1633100

        # Resources
        overview_rsc = await mcp_client.read_resource("tsetmc://market/overview")
        overview_json = json.loads(overview_rsc.contents[0].text)
        assert overview_json["overview"]["market_state"] == "بسته"

        sectors_rsc = await mcp_client.read_resource("tsetmc://market/sectors")
        sectors_json = json.loads(sectors_rsc.contents[0].text)
        assert any(s["code"] == "13" for s in sectors_json["sectors"])

        inst_rsc = await mcp_client.read_resource("tsetmc://instrument/كگل")
        inst_json = json.loads(inst_rsc.contents[0].text)
        assert inst_json["ins_code"] == KGL_INS_CODE
        assert inst_json["quote"]["close"] == pytest.approx(4110.0)


@pytest.mark.asyncio
async def test_buy_queue_detection_and_error_handling() -> None:
    buy_queue_book = {
        "bestLimits": [
            {
                "number": 1,
                "pMeDem": 4120.0,
                "qTitMeDem": 5000000,
                "zOrdMeDem": 120,
                "pMeOf": 0.0,
                "qTitMeOf": 0,
                "zOrdMeOf": 0,
            }
        ]
    }
    transport = _make_tsetmc_transport(
        extra_routes={f"/api/BestLimits/{KGL_INS_CODE}": buy_queue_book}
    )
    server = create_server(client_transport=transport)

    result = await server.call_tool("get_order_book", {"symbol": "کگل", "include_thresholds": True})
    assert result.structured_content["is_buy_queue"] is True
    assert result.structured_content["is_sell_queue"] is False
    assert result.structured_content["queue_value_irr"] == 4120 * 5000000

    with pytest.raises(ToolError, match="Instrument not found"):
        await server.call_tool("get_stock_snapshot", {"symbol": "ناموجود"})

    with pytest.raises(ToolError, match="must not be empty"):
        await server.call_tool("search_instruments", {"query": "   "})

    with pytest.raises(ResourceNotFoundError):
        await server.read_resource("tsetmc://instrument/ناموجود")

    async with MCPTestClient(server) as mcp_client:
        err_res = await mcp_client.call_tool("get_stock_snapshot", {"symbol": "ناموجود"})
        assert err_res.is_error
        assert "ناموجود" in err_res.content[0].text

        with pytest.raises(MCPError):
            await mcp_client.read_resource("tsetmc://instrument/ناموجود")


@pytest.mark.asyncio
async def test_opt_in_db_tools_with_mocked_storage_and_readonly_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_file = tmp_path / "mocked.sqlite"
    transport = _make_tsetmc_transport()

    events: list[str] = []
    fake_rows: list[dict[str, Any]] = [
        {"ins_code": KGL_INS_CODE, "symbol": "کگل", "close": 4110.0}
    ]

    class FakeStore:
        def init_schema(self) -> None:
            events.append("init_schema")
            db_file.write_text("initialized", encoding="utf-8")

        def query_readonly(self, sql: str) -> list[dict[str, Any]]:
            events.append(f"query:{sql}")
            first = sql.strip().split()[0].upper()
            if first not in ("SELECT", "WITH", "PRAGMA"):
                raise StorageError(f"Only read-only SELECT queries allowed (got {first})")
            return list(fake_rows)

        def stats(self) -> dict[str, Any]:
            return {"instruments": 1, "daily_prices": 15}

        def close(self) -> None:
            events.append("close")

    class FakeAsyncSyncService:
        def __init__(self, store: FakeStore, client: Any = None) -> None:
            self.store = store
            self.client = client

        async def sync_all(
            self,
            symbols: list[str] | None = None,
            *,
            sector: str | None = None,
            all_instruments: bool = True,
            include_client_types: bool = True,
        ) -> dict[str, Any]:
            events.append(
                f"sync_all:symbols={symbols}:sector={sector}:all={all_instruments}:ct={include_client_types}"
            )
            return {
                "sectors": 2,
                "instruments": 1,
                "prices": 15,
                "client_types": 15 if include_client_types else 0,
            }

    import tehran_stocks

    fake_storage = SimpleNamespace(
        open_store=lambda target, init_schema=True: FakeStore(),
        AsyncSyncService=FakeAsyncSyncService,
    )
    monkeypatch.setitem(sys.modules, "tehran_stocks.storage", fake_storage)
    monkeypatch.setattr(tehran_stocks, "storage", fake_storage, raising=False)

    server = create_server(db_path=db_file, client_transport=transport)

    # SQLite URI / driver parsing should preserve paths cleanly while ignoring :memory:/non-SQLite URIs.
    assert _local_sqlite_file_path("sqlite:///local.db?mode=ro#frag") == Path("local.db")
    assert _local_sqlite_file_path(f"sqlite+pysqlite:///{tmp_path / 'x.sqlite'}?timeout=5") == (
        tmp_path / "x.sqlite"
    )
    assert _local_sqlite_file_path("sqlite+aiosqlite:///:memory:?cache=shared") is None
    assert _local_sqlite_file_path("postgresql://localhost/tse") is None

    # Query before DB file exists must not create an empty DB file (for both raw path and sqlite+driver URI).
    with pytest.raises(ToolError, match="does not exist"):
        await server.call_tool("query_local_db", {"sql": "SELECT 1"})
    assert not db_file.exists()

    missing_sa_db = tmp_path / "missing_sa.sqlite"
    sa_server = create_server(
        db_path=f"sqlite+pysqlite:///{missing_sa_db}?mode=ro",
        client_transport=transport,
    )
    with pytest.raises(ToolError, match="does not exist"):
        await sa_server.call_tool("query_local_db", {"sql": "SELECT 1"})
    assert not missing_sa_db.exists()

    sync_res = await server.call_tool(
        "sync_local_db",
        {"symbols": ["كگل"], "include_client_type": True},
    )
    assert sync_res.structured_content["symbols"] == ["کگل"]
    assert sync_res.structured_content["sync_result"]["prices"] == 15
    assert sync_res.structured_content["stats"]["instruments"] == 1
    assert "init_schema" in events
    assert "close" in events

    query_res = await server.call_tool(
        "query_local_db",
        {"sql": "SELECT ins_code, symbol, close FROM daily_prices", "limit": 10},
    )
    assert query_res.structured_content["row_count"] == 1
    assert query_res.structured_content["rows"][0]["symbol"] == "کگل"

    async with MCPTestClient(server) as mcp_client:
        bad_query = await mcp_client.call_tool(
            "query_local_db",
            {"sql": "DELETE FROM instruments"},
        )
        assert bad_query.is_error
        assert "read-only" in bad_query.content[0].text.lower()


@pytest.mark.asyncio
async def test_opt_in_db_tools_with_real_sqlite_store(tmp_path: Path) -> None:
    if importlib.util.find_spec("tehran_stocks.storage") is None:
        pytest.skip("tehran_stocks.storage (PR 2) not present in this branch")

    db_file = tmp_path / "real_test.sqlite"
    transport = _make_tsetmc_transport()
    server = create_server(db_path=db_file, client_transport=transport)

    async with MCPTestClient(server) as mcp_client:
        sync_res = await mcp_client.call_tool(
            "sync_local_db",
            {"symbols": ["کگل"], "include_client_type": True},
        )
        assert not sync_res.is_error
        assert sync_res.structured_content["stats"]["daily_prices"] == 15
        assert sync_res.structured_content["stats"]["client_types"] == 15

        select_res = await mcp_client.call_tool(
            "query_local_db",
            {"sql": "SELECT date, close FROM daily_prices ORDER BY date DESC", "limit": 3},
        )
        assert not select_res.is_error
        assert select_res.structured_content["row_count"] == 3
        assert select_res.structured_content["truncated"] is True

        for forbidden_sql in (
            "DELETE FROM daily_prices",
            "DROP TABLE instruments",
            "INSERT INTO sectors (code, name) VALUES ('99', 'test')",
            "UPDATE instruments SET symbol = 'x'",
        ):
            rejected = await mcp_client.call_tool("query_local_db", {"sql": forbidden_sql})
            assert rejected.is_error

        # Verify rows remained untouched after rejected mutations
        count_res = await mcp_client.call_tool(
            "query_local_db",
            {"sql": "SELECT COUNT(*) AS cnt FROM daily_prices"},
        )
        assert not count_res.is_error
        assert count_res.structured_content["rows"][0]["cnt"] == 15


def test_main_cli_parses_flags_and_invokes_server(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recorded: dict[str, Any] = {}

    def fake_run(self: MCPServer, transport: str = "stdio", **kwargs: Any) -> None:
        recorded["server_name"] = self.name
        recorded["tools"] = [t.name for t in self._tool_manager.list_tools()]
        recorded["transport"] = transport
        recorded["kwargs"] = kwargs

    monkeypatch.setattr(MCPServer, "run", fake_run)

    main(
        [
            "--db",
            ":memory:",
            "--transport",
            "streamable-http",
            "--timeout",
            "12.5",
            "--proxy",
            "http://127.0.0.1:8888",
            "--host",
            "127.0.0.1",
            "--port",
            "9123",
        ]
    )

    assert recorded["server_name"] == "tehran-stocks"
    assert "sync_local_db" in recorded["tools"]
    assert "query_local_db" in recorded["tools"]
    assert recorded["transport"] == "streamable-http"
    assert recorded["kwargs"] == {"host": "127.0.0.1", "port": 9123}

    captured = capsys.readouterr()
    assert captured.out == ""

    for bad_port in ("0", "65536", "-1"):
        with pytest.raises(SystemExit) as exc_info:
            main(["--port", bad_port])
        assert exc_info.value.code == 2
        err_capture = capsys.readouterr()
        assert err_capture.out == ""
        assert "1 and 65535" in err_capture.err

    with pytest.raises(ValueError, match="1 and 65535"):
        run_server(port=0)
