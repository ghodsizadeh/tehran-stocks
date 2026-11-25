#!/usr/bin/env python3
"""Build, compact, package, and download TSETMC SQLite data snapshots.

This script lives outside the ``tehran_stocks`` Python package and supports
publishing pre-built SQLite databases via GitHub Releases (e.g. rolling tag
``data-latest``), both from GitHub Actions and from a local machine or VPS.

Examples:
    # 1. Seed a full-market database locally (run once):
    uv run python scripts/data_snapshot.py sync --db ./work/tse.sqlite --mode full --concurrency 4

    # 2. Compact and compress for GitHub Releases:
    uv run python scripts/data_snapshot.py package --db ./work/tse.sqlite --out-dir ./dist-data

    # 3. Download the latest snapshot from GitHub Releases:
    uv run python scripts/data_snapshot.py download --output ./tse.sqlite
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any

import httpx2

DEFAULT_REPO = "ghodsizadeh/tehran-stocks"
DEFAULT_TAG = "data-latest"
MANIFEST_FILENAME = "manifest.json"
CHECKSUMS_FILENAME = "SHA256SUMS"
MANIFEST_SCHEMA_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024.0 or unit == "GiB":
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{size} B"


def _remove_sqlite_sidecars(db_path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{db_path}{suffix}")
        try:
            sidecar.unlink()
        except FileNotFoundError:
            pass


def _find_zstd() -> str:
    exe = shutil.which("zstd")
    if exe:
        return exe
    for candidate in ("/opt/homebrew/bin/zstd", "/usr/local/bin/zstd", "/usr/bin/zstd"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError(
        "zstd executable not found in PATH. Install zstd (e.g. 'brew install zstd' or "
        "'apt-get install zstd') or use '--compression gzip'."
    )


def _compress_file(src: Path, dst: Path, *, compression: str, zstd_level: int = 9) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp_dst = dst.with_name(f".{dst.name}.tmp.{os.getpid()}")
    try:
        if compression == "zstd":
            zstd_bin = _find_zstd()
            subprocess.run(
                [zstd_bin, f"-{zstd_level}", "-T0", "--force", "-q", "-o", str(tmp_dst), str(src)],
                check=True,
            )
        elif compression == "gzip":
            with src.open("rb") as fin, gzip.open(tmp_dst, "wb", compresslevel=6) as fout:
                shutil.copyfileobj(fin, fout, length=1024 * 1024)
        else:
            raise ValueError(f"Unsupported compression format: {compression!r}")
        os.replace(tmp_dst, dst)
    except BaseException:
        tmp_dst.unlink(missing_ok=True)
        raise


def _decompress_file(src: Path, dst: Path, *, compression: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp_dst = dst.with_name(f".{dst.name}.tmp.{os.getpid()}")
    try:
        if compression == "zstd":
            zstd_bin = _find_zstd()
            subprocess.run(
                [zstd_bin, "-d", "--force", "-q", "-o", str(tmp_dst), str(src)],
                check=True,
            )
        elif compression == "gzip":
            with gzip.open(src, "rb") as fin, tmp_dst.open("wb") as fout:
                shutil.copyfileobj(fin, fout, length=1024 * 1024)
        else:
            raise ValueError(f"Unsupported compression format: {compression!r}")
        os.replace(tmp_dst, dst)
    except BaseException:
        tmp_dst.unlink(missing_ok=True)
        raise


def compact_sqlite(db_path: Path, output_path: Path | None = None) -> Path:
    """Checkpoint WAL, copy into a clean single-file SQLite DB, VACUUM, and verify integrity.

    Using ``sqlite3.Connection.backup()`` into a temporary file guarantees that
    the resulting snapshot has ``journal_mode=DELETE``, zero ``-wal``/``-shm``
    sidecar files, and passes ``PRAGMA quick_check`` before replacing the target.
    """
    src_path = db_path.resolve()
    if not src_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {src_path}")

    target_path = (output_path or src_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.compact.",
        suffix=".sqlite",
        dir=str(target_path.parent),
    )
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        src_conn = sqlite3.connect(str(src_path))
        try:
            # Flush WAL frames into the main DB before taking a consistent backup.
            src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            dst_conn = sqlite3.connect(str(tmp_path))
            try:
                src_conn.backup(dst_conn)
                dst_conn.execute("PRAGMA journal_mode=DELETE")
                dst_conn.execute("VACUUM")
                dst_conn.execute("PRAGMA optimize")
                check_rows = dst_conn.execute("PRAGMA quick_check").fetchall()
                if check_rows != [("ok",)]:
                    raise RuntimeError(f"SQLite integrity check failed: {check_rows!r}")
                dst_conn.commit()
            finally:
                dst_conn.close()
        finally:
            src_conn.close()

        _remove_sqlite_sidecars(tmp_path)
        os.replace(tmp_path, target_path)
        _remove_sqlite_sidecars(target_path)
        return target_path
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        _remove_sqlite_sidecars(tmp_path)
        raise


@dataclass(frozen=True, slots=True)
class SyncRunReport:
    """Structured report produced by :func:`run_sync`."""

    mode: str
    scope: str
    duration_seconds: float
    sectors: int
    instruments: int
    prices: int
    adjustments: int
    share_changes: int
    client_types: int
    synced_symbols: int
    skipped_symbols: int
    error_count: int
    error_ratio: float
    sample_errors: dict[str, str]
    passed: bool
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "scope": self.scope,
            "duration_seconds": round(self.duration_seconds, 2),
            "sectors": self.sectors,
            "instruments": self.instruments,
            "prices": self.prices,
            "adjustments": self.adjustments,
            "share_changes": self.share_changes,
            "client_types": self.client_types,
            "synced_symbols": self.synced_symbols,
            "skipped_symbols": self.skipped_symbols,
            "error_count": self.error_count,
            "error_ratio": round(self.error_ratio, 6),
            "sample_errors": dict(self.sample_errors),
            "passed": self.passed,
            "failure_reason": self.failure_reason,
        }


def run_sync(
    db_path: Path,
    *,
    mode: str = "incremental",
    sector: str | None = None,
    symbols: list[str] | None = None,
    include_client_types: bool = True,
    include_adjustments: bool = True,
    include_share_changes: bool = False,
    concurrency: int = 4,
    timeout: float = 30.0,
    proxy: str | None = None,
    max_error_ratio: float = 0.05,
    max_errors: int | None = None,
    allow_empty: bool = False,
    progress_every: int = 50,
    service_factory: Any | None = None,
) -> SyncRunReport:
    """Run ``SyncService.sync_all`` with CI-friendly progress logging and error thresholds."""
    if mode not in {"incremental", "full"}:
        raise ValueError(f"mode must be 'incremental' or 'full', got {mode!r}")
    if sector is not None and symbols is not None:
        raise ValueError("Cannot combine sector and symbols.")
    if not (0.0 <= max_error_ratio <= 1.0):
        raise ValueError("max_error_ratio must be between 0.0 and 1.0.")

    from tehran_stocks.storage import SyncService, open_store

    db_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    scope = (
        f"symbols:{','.join(symbols)}"
        if symbols
        else (f"sector:{sector}" if sector else "all")
    )

    store = open_store(db_path)
    try:
        service_kwargs: dict[str, Any] = {
            "max_concurrency": concurrency,
            "timeout": timeout,
        }
        if proxy:
            service_kwargs["proxy"] = proxy

        if service_factory is not None:
            service = service_factory(store=store, **service_kwargs)
        else:
            service = SyncService(store=store, **service_kwargs)

        def _on_progress(evt: Any) -> None:
            if progress_every <= 0:
                return
            completed = int(getattr(evt, "completed", 0))
            total = int(getattr(evt, "total", 0))
            stage = str(getattr(evt, "stage", "sync"))
            if completed == 1 or completed == total or (completed > 0 and completed % progress_every == 0):
                elapsed = time.monotonic() - started
                print(
                    f"[sync:{stage}] {completed}/{total} ({elapsed:.1f}s)",
                    file=sys.stderr,
                    flush=True,
                )

        result = service.sync_all(
            symbols=symbols,
            sector=sector,
            all_instruments=(symbols is None and sector is None),
            incremental=(mode == "incremental"),
            include_client_types=include_client_types,
            include_adjustments=include_adjustments,
            include_share_changes=include_share_changes,
            fail_fast=False,
            on_progress=_on_progress,
        )
    finally:
        store.close()

    duration = time.monotonic() - started
    errors = dict(getattr(result, "errors", {}) or {})
    error_count = len(errors)
    synced_symbols = int(getattr(result, "synced_symbols", 0))
    skipped_symbols = int(getattr(result, "skipped_symbols", 0))
    succeeded_symbols = synced_symbols + skipped_symbols
    attempted = succeeded_symbols + error_count
    error_ratio = (error_count / attempted) if attempted > 0 else 0.0

    failure_reason: str | None = None
    if error_count > 0 and succeeded_symbols == 0 and not allow_empty:
        failure_reason = f"All {error_count} attempted symbols failed to sync."
    elif attempted > 0 and error_ratio > max_error_ratio:
        failure_reason = (
            f"Error ratio {error_ratio:.2%} ({error_count}/{attempted}) exceeded "
            f"max_error_ratio {max_error_ratio:.2%}."
        )
    elif max_errors is not None and error_count > max_errors:
        failure_reason = f"Error count {error_count} exceeded max_errors {max_errors}."

    sample_errors = dict(list(errors.items())[:20])
    return SyncRunReport(
        mode=mode,
        scope=scope,
        duration_seconds=duration,
        sectors=int(getattr(result, "sectors", 0)),
        instruments=int(getattr(result, "instruments", 0)),
        prices=int(getattr(result, "prices", 0)),
        adjustments=int(getattr(result, "adjustments", 0)),
        share_changes=int(getattr(result, "share_changes", 0)),
        client_types=int(getattr(result, "client_types", 0)),
        synced_symbols=synced_symbols,
        skipped_symbols=skipped_symbols,
        error_count=error_count,
        error_ratio=error_ratio,
        sample_errors=sample_errors,
        passed=(failure_reason is None),
        failure_reason=failure_reason,
    )


def package_snapshot(
    db_path: Path,
    out_dir: Path,
    *,
    compression: str = "zstd",
    asset_name: str | None = None,
    zstd_level: int = 9,
    skip_compact: bool = False,
    tag: str = DEFAULT_TAG,
    repo: str = DEFAULT_REPO,
    sync_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect stats, compact SQLite, compress archive, and emit ``manifest.json`` + ``SHA256SUMS``."""
    from tehran_stocks.storage import open_store

    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")

    # Collect stats BEFORE compacting because open_store() enables WAL mode on SQLite.
    store = open_store(db_path, init_schema=False)
    try:
        db_stats = store.stats()
    finally:
        store.close()

    if not skip_compact:
        compact_sqlite(db_path)

    default_ext = ".zst" if compression == "zstd" else ".gz"
    resolved_asset_name = asset_name or f"tse.sqlite{default_ext}"

    out_dir.mkdir(parents=True, exist_ok=True)
    archive_path = out_dir / resolved_asset_name

    uncompressed_size = db_path.stat().st_size
    uncompressed_sha256 = _sha256_file(db_path)

    _compress_file(db_path, archive_path, compression=compression, zstd_level=zstd_level)

    compressed_size = archive_path.stat().st_size
    compressed_sha256 = _sha256_file(archive_path)

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "updated_at": _utc_now_iso(),
        "repo": repo,
        "tag": tag,
        "asset_name": resolved_asset_name,
        "compression": compression,
        "compressed_size_bytes": compressed_size,
        "compressed_sha256": compressed_sha256,
        "uncompressed_size_bytes": uncompressed_size,
        "uncompressed_sha256": uncompressed_sha256,
        "db_stats": db_stats,
    }
    if sync_summary is not None:
        manifest["sync_summary"] = sync_summary

    manifest_path = out_dir / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest_sha256 = _sha256_file(manifest_path)
    checksums_path = out_dir / CHECKSUMS_FILENAME
    checksums_path.write_text(
        f"{compressed_sha256}  {resolved_asset_name}\n{manifest_sha256}  {MANIFEST_FILENAME}\n",
        encoding="utf-8",
    )
    return manifest


def _release_asset_url(repo: str, tag: str, filename: str) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{filename}"


def _infer_compression(asset_name: str, manifest: dict[str, Any] | None = None) -> str:
    if manifest and isinstance(manifest.get("compression"), str):
        return manifest["compression"]
    if asset_name.endswith(".zst"):
        return "zstd"
    if asset_name.endswith(".gz"):
        return "gzip"
    raise ValueError(f"Cannot infer compression format from asset name: {asset_name!r}")


def download_snapshot(
    output_path: Path,
    *,
    repo: str = DEFAULT_REPO,
    tag: str = DEFAULT_TAG,
    asset_name: str | None = None,
    token: str | None = None,
    timeout: float = 120.0,
    verify: bool = True,
    transport: httpx2.BaseTransport | None = None,
) -> dict[str, Any]:
    """Download, verify, and decompress a snapshot from GitHub Releases."""
    headers: dict[str, str] = {"Accept": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client_kwargs: dict[str, Any] = {
        "follow_redirects": True,
        "timeout": timeout,
        "headers": headers,
    }
    if transport is not None:
        client_kwargs["transport"] = transport

    with httpx2.Client(**client_kwargs) as client:
        manifest_url = _release_asset_url(repo, tag, MANIFEST_FILENAME)
        manifest_resp = client.get(manifest_url, headers={"Accept": "application/json"})
        manifest_resp.raise_for_status()
        manifest: dict[str, Any] = manifest_resp.json()

        resolved_asset = asset_name or str(manifest.get("asset_name") or "tse.sqlite.zst")
        compression = _infer_compression(resolved_asset, manifest)
        asset_url = _release_asset_url(repo, tag, resolved_asset)

        fd, archive_tmp_name = tempfile.mkstemp(
            prefix=f".{resolved_asset}.",
            dir=str(output_path.parent),
        )
        os.close(fd)
        archive_tmp = Path(archive_tmp_name)

        fd2, db_tmp_name = tempfile.mkstemp(
            prefix=f".{output_path.name}.download.",
            suffix=".sqlite",
            dir=str(output_path.parent),
        )
        os.close(fd2)
        db_tmp = Path(db_tmp_name)

        try:
            with client.stream("GET", asset_url) as resp:
                resp.raise_for_status()
                with archive_tmp.open("wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                        fh.write(chunk)

            if verify and manifest.get("compressed_sha256"):
                actual_comp = _sha256_file(archive_tmp)
                expected_comp = str(manifest["compressed_sha256"])
                if actual_comp != expected_comp:
                    raise RuntimeError(
                        f"Compressed SHA-256 mismatch for {resolved_asset}: "
                        f"expected {expected_comp}, got {actual_comp}"
                    )

            _decompress_file(archive_tmp, db_tmp, compression=compression)

            if verify and manifest.get("uncompressed_sha256"):
                actual_raw = _sha256_file(db_tmp)
                expected_raw = str(manifest["uncompressed_sha256"])
                if actual_raw != expected_raw:
                    raise RuntimeError(
                        f"Uncompressed SHA-256 mismatch for {output_path.name}: "
                        f"expected {expected_raw}, got {actual_raw}"
                    )

            os.replace(db_tmp, output_path)
            _remove_sqlite_sidecars(output_path)
        except BaseException:
            db_tmp.unlink(missing_ok=True)
            raise
        finally:
            archive_tmp.unlink(missing_ok=True)

    return manifest


def render_markdown_summary(manifest: dict[str, Any]) -> str:
    """Render a concise Markdown summary suitable for Release notes or GitHub Step Summary."""
    stats = manifest.get("db_stats") or {}
    sync = manifest.get("sync_summary") or {}
    asset_name = manifest.get("asset_name", "tse.sqlite.zst")
    tag = manifest.get("tag", DEFAULT_TAG)
    repo = manifest.get("repo", DEFAULT_REPO)
    download_url = _release_asset_url(repo, tag, asset_name)

    lines = [
        f"## TSETMC SQLite Snapshot (`{tag}`)",
        "",
        f"- **Updated (UTC):** `{manifest.get('updated_at', 'unknown')}`",
        f"- **Asset:** `{asset_name}` ({_format_bytes(int(manifest.get('compressed_size_bytes', 0)))} compressed / "
        f"{_format_bytes(int(manifest.get('uncompressed_size_bytes', 0)))} uncompressed)",
        f"- **SHA-256 (compressed):** `{manifest.get('compressed_sha256', '')}`",
        f"- **SHA-256 (SQLite):** `{manifest.get('uncompressed_sha256', '')}`",
        "",
        "### Database Coverage",
        "",
        "| Metric | Value |",
        "| :--- | ---: |",
        f"| Sectors | {int(stats.get('sectors', 0)):,} |",
        f"| Instruments | {int(stats.get('instruments', 0)):,} |",
        f"| Daily Prices | {int(stats.get('daily_prices', 0)):,} |",
        f"| Client Types | {int(stats.get('client_types', 0)):,} |",
        f"| Price Adjustments | {int(stats.get('price_adjustments', 0)):,} |",
        f"| Share Changes | {int(stats.get('share_changes', 0)):,} |",
        f"| Price Date Range | `{stats.get('min_price_date')}` → `{stats.get('max_price_date')}` |",
        f"| Client-Type Date Range | `{stats.get('min_client_type_date')}` → `{stats.get('max_client_type_date')}` |",
    ]

    if sync:
        lines.extend(
            [
                "",
                "### Last Sync Run",
                "",
                f"- **Mode / Scope:** `{sync.get('mode')}` / `{sync.get('scope')}`",
                f"- **Duration:** `{sync.get('duration_seconds')}s`",
                f"- **Symbols Synced / Skipped / Errors:** "
                f"`{sync.get('synced_symbols', 0)}` / `{sync.get('skipped_symbols', 0)}` / `{sync.get('error_count', 0)}` "
                f"({float(sync.get('error_ratio', 0.0)):.2%})",
            ]
        )

    lines.extend(
        [
            "",
            "### Quick Download",
            "",
            "```bash",
            f"curl -fL {download_url} -o {asset_name}",
            f"zstd -d {asset_name} -o tse.sqlite"
            if manifest.get("compression") == "zstd"
            else f"gunzip -c {asset_name} > tse.sqlite",
            "tse db status --db ./tse.sqlite",
            "tse db sync --db ./tse.sqlite --incremental --client-type",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_symbols(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build, compact, package, and download TSETMC SQLite snapshots."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # sync
    p_sync = sub.add_parser("sync", help="Sync TSETMC data into a SQLite database.")
    p_sync.add_argument("--db", required=True, type=Path, help="Path to SQLite database.")
    p_sync.add_argument(
        "--mode",
        choices=("incremental", "full"),
        default="incremental",
        help="Sync mode (default: incremental).",
    )
    p_sync.add_argument("--sector", default=None, help="Optional sector code filter (e.g. 34).")
    p_sync.add_argument(
        "--symbols",
        default=None,
        help="Optional comma-separated symbol list (e.g. کگل,فولاد).",
    )
    p_sync.add_argument(
        "--client-type",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include individual/institutional flow history (default: true).",
    )
    p_sync.add_argument(
        "--adjustments",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include price adjustments (default: true).",
    )
    p_sync.add_argument(
        "--share-changes",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include historical share count changes (default: false).",
    )
    p_sync.add_argument("--concurrency", type=int, default=4, help="Max concurrent requests (default: 4).")
    p_sync.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds (default: 30).")
    p_sync.add_argument(
        "--proxy",
        default=None,
        help="Optional HTTP/SOCKS proxy URL (defaults to TSETMC_PROXY env var if set).",
    )
    p_sync.add_argument(
        "--max-error-ratio",
        type=float,
        default=0.05,
        help="Max tolerated symbol error ratio before failing (default: 0.05).",
    )
    p_sync.add_argument(
        "--max-errors",
        type=int,
        default=None,
        help="Optional hard cap on tolerated symbol errors.",
    )
    p_sync.add_argument(
        "--allow-empty",
        action="store_true",
        help="Do not fail if synced_symbols == 0.",
    )
    p_sync.add_argument(
        "--progress-every",
        type=int,
        default=50,
        help="Log progress every N completed symbols to stderr (0 disables).",
    )
    p_sync.add_argument(
        "--summary-out",
        type=Path,
        default=None,
        help="Optional path to write JSON sync summary.",
    )

    # compact
    p_compact = sub.add_parser("compact", help="Checkpoint WAL, backup, VACUUM, and verify SQLite DB.")
    p_compact.add_argument("--db", required=True, type=Path, help="Path to source SQLite database.")
    p_compact.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path (defaults to in-place atomic replacement).",
    )

    # package
    p_pkg = sub.add_parser("package", help="Compact, compress, and generate manifest.json + SHA256SUMS.")
    p_pkg.add_argument("--db", required=True, type=Path, help="Path to SQLite database.")
    p_pkg.add_argument("--out-dir", required=True, type=Path, help="Output directory for release assets.")
    p_pkg.add_argument(
        "--compression",
        choices=("zstd", "gzip"),
        default="zstd",
        help="Compression format (default: zstd).",
    )
    p_pkg.add_argument("--asset-name", default=None, help="Override compressed asset filename.")
    p_pkg.add_argument("--zstd-level", type=int, default=9, help="zstd compression level (default: 9).")
    p_pkg.add_argument("--skip-compact", action="store_true", help="Skip SQLite compact step.")
    p_pkg.add_argument("--tag", default=DEFAULT_TAG, help=f"GitHub Release tag (default: {DEFAULT_TAG}).")
    p_pkg.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub repo (default: {DEFAULT_REPO}).")
    p_pkg.add_argument(
        "--sync-summary",
        type=Path,
        default=None,
        help="Optional JSON file from 'sync --summary-out' to embed in manifest.json.",
    )

    # download
    p_dl = sub.add_parser("download", help="Download, verify, and decompress a GitHub Release snapshot.")
    p_dl.add_argument("--output", type=Path, default=Path("./tse.sqlite"), help="Target SQLite path.")
    p_dl.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub repo (default: {DEFAULT_REPO}).")
    p_dl.add_argument("--tag", default=DEFAULT_TAG, help=f"GitHub Release tag (default: {DEFAULT_TAG}).")
    p_dl.add_argument("--asset-name", default=None, help="Override asset filename from manifest.json.")
    p_dl.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout seconds (default: 120).")
    p_dl.add_argument(
        "--verify",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Verify SHA-256 checksums against manifest.json (default: true).",
    )

    # render-summary
    p_sum = sub.add_parser("render-summary", help="Render Markdown summary from manifest.json.")
    p_sum.add_argument("--manifest", required=True, type=Path, help="Path to manifest.json.")
    p_sum.add_argument("--output", type=Path, default=None, help="Optional output Markdown file.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "sync":
        proxy = args.proxy or os.environ.get("TSETMC_PROXY") or None
        report = run_sync(
            args.db,
            mode=args.mode,
            sector=args.sector or None,
            symbols=_parse_symbols(args.symbols),
            include_client_types=args.client_type,
            include_adjustments=args.adjustments,
            include_share_changes=args.share_changes,
            concurrency=args.concurrency,
            timeout=args.timeout,
            proxy=proxy,
            max_error_ratio=args.max_error_ratio,
            max_errors=args.max_errors,
            allow_empty=args.allow_empty,
            progress_every=args.progress_every,
        )
        payload = report.to_dict()
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.summary_out is not None:
            args.summary_out.parent.mkdir(parents=True, exist_ok=True)
            args.summary_out.write_text(serialized + "\n", encoding="utf-8")
        print(serialized)
        if not report.passed:
            print(f"ERROR: {report.failure_reason}", file=sys.stderr)
            return 1
        return 0

    if args.command == "compact":
        out = compact_sqlite(args.db, args.output)
        print(json.dumps({"compacted": str(out), "size_bytes": out.stat().st_size}, indent=2))
        return 0

    if args.command == "package":
        sync_summary: dict[str, Any] | None = None
        if args.sync_summary is not None and args.sync_summary.exists():
            sync_summary = json.loads(args.sync_summary.read_text(encoding="utf-8"))
        manifest = package_snapshot(
            args.db,
            args.out_dir,
            compression=args.compression,
            asset_name=args.asset_name,
            zstd_level=args.zstd_level,
            skip_compact=args.skip_compact,
            tag=args.tag,
            repo=args.repo,
            sync_summary=sync_summary,
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    if args.command == "download":
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or None
        manifest = download_snapshot(
            args.output,
            repo=args.repo,
            tag=args.tag,
            asset_name=args.asset_name,
            token=token,
            timeout=args.timeout,
            verify=args.verify,
        )
        print(
            json.dumps(
                {
                    "output": str(args.output.resolve()),
                    "tag": manifest.get("tag"),
                    "updated_at": manifest.get("updated_at"),
                    "size_bytes": args.output.stat().st_size,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "render-summary":
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        md = render_markdown_summary(manifest)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(md, encoding="utf-8")
        else:
            print(md)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
