"""Offline unit tests for scripts/data_snapshot.py."""

from __future__ import annotations

from datetime import date
import importlib.util
import json
from pathlib import Path
import sqlite3
from types import ModuleType
from typing import Any

import httpx2
import pytest

from tehran_stocks.storage import SyncResult, open_store
from tehran_stocks.types.instrument import Instrument
from tehran_stocks.types.market import Sector
from tehran_stocks.types.price import DailyBar

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "data_snapshot.py"


def _load_snapshot_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("data_snapshot", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


snapshot = _load_snapshot_module()


def _seed_sample_db(db_path: Path) -> None:
    store = open_store(db_path)
    try:
        store.upsert_sectors([Sector(code="13", name="کانه های فلزی", type="IndustrialGroup")])
        store.upsert_instruments(
            [
                Instrument(
                    ins_code="35700344742885862",
                    symbol="کگل",
                    name="صنعتی و معدنی گل گهر",
                    isin="IRO1GLGO0001",
                    sector_code="13",
                    sector_name="کانه های فلزی",
                )
            ]
        )
        store.upsert_prices(
            [
                DailyBar(
                    ins_code="35700344742885862",
                    date=date(2025, 1, 15),
                    open=5000.0,
                    high=5200.0,
                    low=4950.0,
                    close=5150.0,
                    last=5100.0,
                    yesterday=4900.0,
                    volume=12_345_678,
                    value=63_000_000_000,
                    trade_count=4200,
                )
            ]
        )
    finally:
        store.close()


def test_compact_sqlite_removes_wal_and_preserves_data(tmp_path: Path) -> None:
    db_path = tmp_path / "tse.sqlite"
    _seed_sample_db(db_path)

    # Open a WAL connection and write a row without closing to ensure WAL mode is active,
    # then close and compact.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "INSERT OR REPLACE INTO sync_meta (key, value, updated_at) "
        "VALUES ('test_key', 'test_val', '2025-01-15T00:00:00Z')"
    )
    conn.commit()
    conn.close()

    out = snapshot.compact_sqlite(db_path)
    assert out == db_path.resolve()
    assert not Path(f"{db_path}-wal").exists()
    assert not Path(f"{db_path}-shm").exists()

    verify_conn = sqlite3.connect(str(db_path))
    try:
        mode = verify_conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert str(mode).lower() == "delete"
        assert verify_conn.execute("PRAGMA quick_check").fetchall() == [("ok",)]
    finally:
        verify_conn.close()

    store = open_store(db_path, init_schema=False)
    try:
        stats = store.stats()
        assert stats["sectors"] == 1
        assert stats["instruments"] == 1
        assert stats["daily_prices"] == 1
        assert store.get_sync_meta("test_key") == "test_val"
    finally:
        store.close()


@pytest.mark.parametrize("compression", ["gzip", "zstd"])
def test_package_and_download_roundtrip(tmp_path: Path, compression: str) -> None:
    if compression == "zstd":
        try:
            snapshot._find_zstd()
        except RuntimeError:
            pytest.skip("zstd binary not installed in this environment")

    src_db = tmp_path / "work" / "tse.sqlite"
    _seed_sample_db(src_db)
    out_dir = tmp_path / "dist-data"

    sync_summary = {
        "mode": "incremental",
        "scope": "all",
        "duration_seconds": 12.5,
        "synced_symbols": 100,
        "skipped_symbols": 0,
        "error_count": 1,
        "error_ratio": 0.01,
        "passed": True,
    }
    manifest = snapshot.package_snapshot(
        src_db,
        out_dir,
        compression=compression,
        tag="data-latest",
        repo="ghodsizadeh/tehran-stocks",
        sync_summary=sync_summary,
    )

    asset_name = manifest["asset_name"]
    assert asset_name.endswith(".zst" if compression == "zstd" else ".gz")
    archive_path = out_dir / asset_name
    manifest_path = out_dir / "manifest.json"
    checksums_path = out_dir / "SHA256SUMS"

    assert archive_path.exists()
    assert manifest_path.exists()
    assert checksums_path.exists()
    assert manifest["db_stats"]["daily_prices"] == 1
    assert manifest["sync_summary"]["synced_symbols"] == 100
    assert manifest["compressed_sha256"] in checksums_path.read_text(encoding="utf-8")

    # Verify packaged SQLite remained in DELETE journal mode (stats were read before compacting).
    conn = sqlite3.connect(str(src_db))
    try:
        assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "delete"
    finally:
        conn.close()

    # Render Markdown summary
    md = snapshot.render_markdown_summary(manifest)
    assert "TSETMC SQLite Snapshot (`data-latest`)" in md
    assert asset_name in md
    assert "2025-01-15" in md

    # Download roundtrip using MockTransport
    manifest_bytes = manifest_path.read_bytes()
    archive_bytes = archive_path.read_bytes()

    def _handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/manifest.json"):
            return httpx2.Response(200, content=manifest_bytes)
        if request.url.path.endswith(f"/{asset_name}"):
            return httpx2.Response(200, content=archive_bytes)
        return httpx2.Response(404)

    downloaded_db = tmp_path / "downloaded" / "tse.sqlite"
    dl_manifest = snapshot.download_snapshot(
        downloaded_db,
        repo="ghodsizadeh/tehran-stocks",
        tag="data-latest",
        transport=httpx2.MockTransport(_handler),
    )
    assert dl_manifest["compressed_sha256"] == manifest["compressed_sha256"]
    assert downloaded_db.exists()

    store = open_store(downloaded_db, init_schema=False)
    try:
        bars = store.get_prices("کگل")
        assert len(bars) == 1
        assert bars[0].close == 5150.0
    finally:
        store.close()


def test_download_rejects_corrupted_checksum_and_preserves_existing_file(tmp_path: Path) -> None:
    src_db = tmp_path / "src.sqlite"
    _seed_sample_db(src_db)
    out_dir = tmp_path / "dist"
    manifest = snapshot.package_snapshot(src_db, out_dir, compression="gzip")

    target_db = tmp_path / "existing.sqlite"
    target_db.write_bytes(b"original-content")

    manifest_bytes = (out_dir / "manifest.json").read_bytes()
    corrupted_bytes = b"corrupted-archive-bytes"

    def _handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/manifest.json"):
            return httpx2.Response(200, content=manifest_bytes)
        if request.url.path.endswith(f"/{manifest['asset_name']}"):
            return httpx2.Response(200, content=corrupted_bytes)
        return httpx2.Response(404)

    with pytest.raises(RuntimeError, match="Compressed SHA-256 mismatch"):
        snapshot.download_snapshot(
            target_db,
            transport=httpx2.MockTransport(_handler),
        )

    assert target_db.read_bytes() == b"original-content"


class _FakeSyncService:
    def __init__(self, result: SyncResult) -> None:
        self._result = result
        self.calls: list[dict[str, Any]] = []

    def sync_all(self, **kwargs: Any) -> SyncResult:
        self.calls.append(kwargs)
        cb = kwargs.get("on_progress")
        if callable(cb):
            cb(type("P", (), {"stage": "prices", "completed": 1, "total": 1})())
        return self._result


def test_run_sync_allows_partial_errors_within_threshold(tmp_path: Path) -> None:
    fake = _FakeSyncService(
        SyncResult(
            sectors=66,
            instruments=100,
            prices=500,
            synced_symbols=19,
            errors={"HALTED1": "HTTP 404"},
        )
    )
    report = snapshot.run_sync(
        tmp_path / "tse.sqlite",
        mode="incremental",
        max_error_ratio=0.05,
        service_factory=lambda **_: fake,
    )
    assert report.passed is True
    assert report.failure_reason is None
    assert report.error_count == 1
    assert report.error_ratio == pytest.approx(0.05)
    assert fake.calls[0]["incremental"] is True
    assert fake.calls[0]["all_instruments"] is True


def test_run_sync_fails_when_error_ratio_exceeds_threshold(tmp_path: Path) -> None:
    fake = _FakeSyncService(
        SyncResult(
            synced_symbols=8,
            errors={"SYM1": "timeout", "SYM2": "timeout"},
        )
    )
    report = snapshot.run_sync(
        tmp_path / "tse.sqlite",
        mode="incremental",
        max_error_ratio=0.05,
        service_factory=lambda **_: fake,
    )
    assert report.passed is False
    assert report.failure_reason is not None
    assert "exceeded max_error_ratio" in report.failure_reason


def test_run_sync_fails_when_all_symbols_fail(tmp_path: Path) -> None:
    fake = _FakeSyncService(
        SyncResult(
            synced_symbols=0,
            errors={"SYM1": "403", "SYM2": "403"},
        )
    )
    report = snapshot.run_sync(
        tmp_path / "tse.sqlite",
        mode="incremental",
        max_error_ratio=1.0,
        service_factory=lambda **_: fake,
    )
    assert report.passed is False
    assert "All 2 attempted symbols failed" in (report.failure_reason or "")


def test_cli_package_and_render_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "tse.sqlite"
    _seed_sample_db(db_path)
    out_dir = tmp_path / "out"
    notes_path = tmp_path / "notes.md"

    rc_pkg = snapshot.main(
        [
            "package",
            "--db",
            str(db_path),
            "--out-dir",
            str(out_dir),
            "--compression",
            "gzip",
        ]
    )
    assert rc_pkg == 0
    manifest_path = out_dir / "manifest.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["compression"] == "gzip"

    rc_md = snapshot.main(
        [
            "render-summary",
            "--manifest",
            str(manifest_path),
            "--output",
            str(notes_path),
        ]
    )
    assert rc_md == 0
    assert "tse.sqlite.gz" in notes_path.read_text(encoding="utf-8")
