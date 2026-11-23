"""Concurrent, incremental TSETMC synchronization services."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Any

import httpx2

from tehran_stocks.client.base import AsyncTSETMCClient
from tehran_stocks.exceptions import StorageError
from tehran_stocks.storage._sql import (
    normalize_identifier,
    normalize_sector_code,
    utc_now_iso,
)
from tehran_stocks.storage.protocol import StorageBackend
from tehran_stocks.types._base import SerializableMixin
from tehran_stocks.types.instrument import Instrument
from tehran_stocks.types.market import Sector
from tehran_stocks.utils.persian import normalize_persian

_FLOW_MARKET_TITLES: dict[int, str] = {
    1: "بازار بورس",
    2: "بازار فرابورس",
    3: "بازار مشتقه",
    4: "بازار پایه فرابورس",
    7: "بورس کالا",
}


@dataclass(frozen=True, slots=True)
class SyncProgress(SerializableMixin):
    """Progress notification emitted during sync operations."""

    stage: str
    completed: int
    total: int
    symbol: str = ""
    rows: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class SyncResult(SerializableMixin):
    """Aggregate summary returned by ``SyncService`` and ``AsyncSyncService``."""

    sectors: int = 0
    instruments: int = 0
    prices: int = 0
    adjustments: int = 0
    share_changes: int = 0
    client_types: int = 0
    synced_symbols: int = 0
    skipped_symbols: int = 0
    errors: dict[str, str] = field(default_factory=dict)


def _emit_progress(
    callback: Callable[[SyncProgress], Any] | None,
    progress: SyncProgress,
) -> None:
    if callback is not None:
        callback(progress)


def _set_meta_if_supported(store: StorageBackend, key: str, value: str) -> None:
    setter = getattr(store, "set_sync_meta", None)
    if callable(setter):
        setter(key, value)


def _parse_static_sectors(static_data: Any) -> list[Sector]:
    rows = static_data.get("staticData") if isinstance(static_data, Mapping) else static_data
    if not isinstance(rows, list):
        return []
    sectors: list[Sector] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_type = str(row.get("type") or "").strip()
        if row_type and row_type != "IndustrialGroup":
            continue
        code = normalize_sector_code(row.get("code"))
        if not code:
            continue
        name = normalize_persian(str(row.get("name") or "")).strip()
        sectors.append(Sector(code=code, name=name, type=row_type or "IndustrialGroup"))
    return sectors


def _parse_watch_instruments(
    watch_data: Any,
    sector_names: Mapping[str, str],
) -> list[Instrument]:
    rows = watch_data.get("marketwatch") if isinstance(watch_data, Mapping) else watch_data
    if not isinstance(rows, list):
        return []

    instruments: list[Instrument] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        inst = Instrument.from_tsetmc(row)
        ins_code = inst.ins_code.strip()
        if not ins_code or ins_code == "0":
            continue
        sec_code = normalize_sector_code(inst.sector_code)
        market = inst.market or (
            _FLOW_MARKET_TITLES.get(inst.flow, "") if inst.flow is not None else ""
        )
        instruments.append(
            replace(
                inst,
                ins_code=ins_code,
                sector_code=sec_code,
                sector_name=inst.sector_name or sector_names.get(sec_code, ""),
                market=market,
            )
        )
    return instruments


def _compute_fetch_days(
    last_date: date | None,
    *,
    incremental: bool,
    overlap_days: int,
) -> int:
    if not incremental or last_date is None:
        return 0
    gap = max((date.today() - last_date).days, 0) + max(overlap_days, 0)
    if gap > 180:
        return 0
    return max(gap + 5, 10)


def _filter_incremental(
    records: Sequence[Any],
    last_date: date | None,
    *,
    incremental: bool,
    overlap_days: int,
) -> list[Any]:
    if not incremental or last_date is None:
        return list(records)
    cutoff = last_date - timedelta(days=max(overlap_days, 0))
    if overlap_days > 0:
        return [rec for rec in records if rec.date >= cutoff]
    return [rec for rec in records if rec.date > last_date]


class AsyncSyncService:
    """Async incremental sync service backed by ``AsyncTSETMCClient`` and ``StorageBackend``."""

    def __init__(
        self,
        store: StorageBackend,
        client: AsyncTSETMCClient | None = None,
        *,
        max_concurrency: int = 8,
        transport: httpx2.AsyncBaseTransport | None = None,
        **client_kwargs: Any,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        self.store = store
        self.max_concurrency = max_concurrency
        self._client = client
        self._owns_client = client is None
        self._transport = transport
        self._client_kwargs = dict(client_kwargs)
        self._store_lock = asyncio.Lock()

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> AsyncSyncService:
        if self._client is None:
            self._client = AsyncTSETMCClient(
                max_concurrency=self.max_concurrency,
                transport=self._transport,
                **self._client_kwargs,
            )
            self._owns_client = True
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._client is not None and self._owns_client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    async def _run_with_client(
        self,
        client_override: AsyncTSETMCClient | None,
        fn: Callable[[AsyncTSETMCClient], Awaitable[SyncResult]],
    ) -> SyncResult:
        if client_override is not None:
            return await fn(client_override)
        if self._client is not None:
            return await fn(self._client)
        async with AsyncTSETMCClient(
            max_concurrency=self.max_concurrency,
            transport=self._transport,
            **self._client_kwargs,
        ) as ephemeral_client:
            return await fn(ephemeral_client)

    async def _sync_instruments(
        self,
        client: AsyncTSETMCClient,
        *,
        on_progress: Callable[[SyncProgress], Any] | None = None,
    ) -> SyncResult:
        static_data, watch_data = await asyncio.gather(
            client.transport.get_json("/api/StaticData/GetStaticData"),
            client.transport.get_json("/api/ClosingPrice/GetMarketWatch"),
        )

        sectors = _parse_static_sectors(static_data)
        sector_names = {s.code: s.name for s in sectors}
        instruments = _parse_watch_instruments(watch_data, sector_names)

        async with self._store_lock:
            sector_count = self.store.upsert_sectors(sectors)
            instrument_count = self.store.upsert_instruments(instruments)
            now = utc_now_iso()
            _set_meta_if_supported(self.store, "last_sectors_sync", now)
            _set_meta_if_supported(self.store, "last_instruments_sync", now)

        _emit_progress(
            on_progress,
            SyncProgress(
                stage="instruments",
                completed=1,
                total=1,
                rows=instrument_count,
            ),
        )
        return SyncResult(sectors=sector_count, instruments=instrument_count)

    async def sync_instruments(
        self,
        *,
        on_progress: Callable[[SyncProgress], Any] | None = None,
    ) -> SyncResult:
        """Sync all sectors and instruments in 2 HTTP calls (``GetStaticData`` + ``GetMarketWatch``)."""
        return await self._run_with_client(
            None,
            lambda client: self._sync_instruments(client, on_progress=on_progress),
        )

    async def _resolve_targets(
        self,
        client: AsyncTSETMCClient,
        *,
        symbols: Sequence[str | int] | None,
        sector: str | None,
        all_instruments: bool,
    ) -> tuple[list[tuple[str, str]], dict[str, str]]:
        if symbols is None and sector is None and not all_instruments:
            raise ValueError("Specify at least one of symbols, sector, or all_instruments=True")

        targets: list[tuple[str, str]] = []
        seen: set[str] = set()
        resolution_errors: dict[str, str] = {}

        if symbols is not None:
            for raw_symbol in symbols:
                label = str(raw_symbol)
                resolved = self.store.resolve_ins_code(raw_symbol)
                if resolved is None:
                    try:
                        resolved = await client.resolve(raw_symbol)
                    except Exception as exc:
                        resolution_errors[label] = str(exc)
                        continue
                if resolved not in seen:
                    seen.add(resolved)
                    targets.append((label, resolved))
            return targets, resolution_errors

        if all_instruments:
            stored = self.store.list_instruments()
            if not stored:
                await self._sync_instruments(client)
                stored = self.store.list_instruments()
        else:
            assert sector is not None
            norm_sector = normalize_sector_code(sector)
            stored = self.store.list_instruments(sector_code=norm_sector)
            if not stored and int(self.store.stats().get("instruments", 0)) == 0:
                await self._sync_instruments(client)
                stored = self.store.list_instruments(sector_code=norm_sector)

        for inst in stored:
            if inst.ins_code not in seen:
                seen.add(inst.ins_code)
                targets.append((inst.symbol or inst.ins_code, inst.ins_code))
        return targets, resolution_errors

    async def _run_symbol_batch(
        self,
        client: AsyncTSETMCClient,
        *,
        stage: str,
        symbols: Sequence[str | int] | None,
        sector: str | None,
        all_instruments: bool,
        fail_fast: bool,
        on_progress: Callable[[SyncProgress], Any] | None,
        sync_one: Callable[[AsyncTSETMCClient, str], Awaitable[dict[str, int]]],
    ) -> SyncResult:
        targets, errors = await self._resolve_targets(
            client,
            symbols=symbols,
            sector=sector,
            all_instruments=all_instruments,
        )
        if fail_fast and errors:
            first_sym, first_err = next(iter(errors.items()))
            raise StorageError(f"Failed to resolve {first_sym!r}: {first_err}")

        total = len(targets)
        if total == 0:
            return SyncResult(errors=errors)

        semaphore = asyncio.Semaphore(self.max_concurrency)
        completed = 0
        totals = {
            "prices": 0,
            "adjustments": 0,
            "share_changes": 0,
            "client_types": 0,
        }
        synced_symbols = 0
        skipped_symbols = 0

        async def _worker(label: str, ins_code: str) -> None:
            nonlocal completed, synced_symbols, skipped_symbols

            async with semaphore:
                try:
                    counts = await sync_one(client, ins_code)
                    primary_rows = counts.get(stage, 0)
                    for key, val in counts.items():
                        if key in totals:
                            totals[key] += val
                    if primary_rows > 0:
                        synced_symbols += 1
                    else:
                        skipped_symbols += 1

                    completed += 1
                    _emit_progress(
                        on_progress,
                        SyncProgress(
                            stage=stage,
                            completed=completed,
                            total=total,
                            symbol=label,
                            rows=primary_rows,
                        ),
                    )
                except Exception as exc:
                    if fail_fast:
                        raise
                    errors[normalize_identifier(label) or ins_code] = str(exc)
                    completed += 1
                    _emit_progress(
                        on_progress,
                        SyncProgress(
                            stage=stage,
                            completed=completed,
                            total=total,
                            symbol=label,
                            error=str(exc),
                        ),
                    )

        await asyncio.gather(*(_worker(label, code) for label, code in targets))
        return SyncResult(
            prices=totals["prices"],
            adjustments=totals["adjustments"],
            share_changes=totals["share_changes"],
            client_types=totals["client_types"],
            synced_symbols=synced_symbols,
            skipped_symbols=skipped_symbols,
            errors=errors,
        )

    async def _sync_prices(
        self,
        client: AsyncTSETMCClient,
        symbols: Sequence[str | int] | None = None,
        *,
        sector: str | None = None,
        all_instruments: bool = False,
        incremental: bool = True,
        overlap_days: int = 0,
        include_adjustments: bool = True,
        include_share_changes: bool = False,
        fail_fast: bool = False,
        on_progress: Callable[[SyncProgress], Any] | None = None,
    ) -> SyncResult:
        async def _sync_one(active_client: AsyncTSETMCClient, ins_code: str) -> dict[str, int]:
            async with self._store_lock:
                last_date = self.store.get_last_price_date(ins_code) if incremental else None

            fetch_days = _compute_fetch_days(
                last_date,
                incremental=incremental,
                overlap_days=overlap_days,
            )
            tasks: list[Awaitable[Any]] = [
                active_client.prices.history(ins_code, days=fetch_days, adjusted=False)
            ]
            if include_adjustments:
                tasks.append(active_client.prices.adjustments(ins_code))
            if include_share_changes:
                tasks.append(active_client.instruments.share_changes(ins_code))

            results = await asyncio.gather(*tasks)
            bars = _filter_incremental(
                results[0],
                last_date,
                incremental=incremental,
                overlap_days=overlap_days,
            )
            idx = 1
            adjs = results[idx] if include_adjustments else []
            if include_adjustments:
                idx += 1
            changes = results[idx] if include_share_changes else []

            async with self._store_lock:
                written_prices = self.store.upsert_prices(bars)
                written_adjs = self.store.upsert_adjustments(adjs) if adjs else 0
                written_changes = self.store.upsert_share_changes(changes) if changes else 0
                if written_prices > 0 or written_adjs > 0 or written_changes > 0:
                    _set_meta_if_supported(
                        self.store,
                        f"last_prices_sync:{ins_code}",
                        utc_now_iso(),
                    )

            return {
                "prices": written_prices,
                "adjustments": written_adjs,
                "share_changes": written_changes,
            }

        return await self._run_symbol_batch(
            client,
            stage="prices",
            symbols=symbols,
            sector=sector,
            all_instruments=all_instruments,
            fail_fast=fail_fast,
            on_progress=on_progress,
            sync_one=_sync_one,
        )

    async def sync_prices(
        self,
        symbols: Sequence[str | int] | None = None,
        *,
        sector: str | None = None,
        all_instruments: bool = False,
        incremental: bool = True,
        overlap_days: int = 0,
        include_adjustments: bool = True,
        include_share_changes: bool = False,
        fail_fast: bool = False,
        on_progress: Callable[[SyncProgress], Any] | None = None,
    ) -> SyncResult:
        """Incrementally sync daily OHLCV prices (and adjustments) for matching targets."""
        return await self._run_with_client(
            None,
            lambda client: self._sync_prices(
                client,
                symbols=symbols,
                sector=sector,
                all_instruments=all_instruments,
                incremental=incremental,
                overlap_days=overlap_days,
                include_adjustments=include_adjustments,
                include_share_changes=include_share_changes,
                fail_fast=fail_fast,
                on_progress=on_progress,
            ),
        )

    async def _sync_client_types(
        self,
        client: AsyncTSETMCClient,
        symbols: Sequence[str | int] | None = None,
        *,
        sector: str | None = None,
        all_instruments: bool = False,
        incremental: bool = True,
        overlap_days: int = 0,
        fail_fast: bool = False,
        on_progress: Callable[[SyncProgress], Any] | None = None,
    ) -> SyncResult:
        async def _sync_one(active_client: AsyncTSETMCClient, ins_code: str) -> dict[str, int]:
            async with self._store_lock:
                last_date = (
                    self.store.get_last_client_type_date(ins_code) if incremental else None
                )
            records = await active_client.client_type.history(ins_code)
            filtered = _filter_incremental(
                records,
                last_date,
                incremental=incremental,
                overlap_days=overlap_days,
            )

            async with self._store_lock:
                written = self.store.upsert_client_types(filtered)
                if written > 0:
                    _set_meta_if_supported(
                        self.store,
                        f"last_client_types_sync:{ins_code}",
                        utc_now_iso(),
                    )

            return {"client_types": written}

        return await self._run_symbol_batch(
            client,
            stage="client_types",
            symbols=symbols,
            sector=sector,
            all_instruments=all_instruments,
            fail_fast=fail_fast,
            on_progress=on_progress,
            sync_one=_sync_one,
        )

    async def sync_client_types(
        self,
        symbols: Sequence[str | int] | None = None,
        *,
        sector: str | None = None,
        all_instruments: bool = False,
        incremental: bool = True,
        overlap_days: int = 0,
        fail_fast: bool = False,
        on_progress: Callable[[SyncProgress], Any] | None = None,
    ) -> SyncResult:
        """Incrementally sync daily institutional/individual flow for matching targets."""
        return await self._run_with_client(
            None,
            lambda client: self._sync_client_types(
                client,
                symbols=symbols,
                sector=sector,
                all_instruments=all_instruments,
                incremental=incremental,
                overlap_days=overlap_days,
                fail_fast=fail_fast,
                on_progress=on_progress,
            ),
        )

    async def sync_all(
        self,
        symbols: Sequence[str | int] | None = None,
        *,
        sector: str | None = None,
        all_instruments: bool = True,
        incremental: bool = True,
        include_client_types: bool = True,
        include_adjustments: bool = True,
        include_share_changes: bool = False,
        fail_fast: bool = False,
        on_progress: Callable[[SyncProgress], Any] | None = None,
    ) -> SyncResult:
        """Sync instruments/sectors followed by prices and optional client-type flow."""
        use_all = all_instruments if (symbols is None and sector is None) else False

        async def _run_all(client: AsyncTSETMCClient) -> SyncResult:
            inst_res = await self._sync_instruments(client, on_progress=on_progress)
            if symbols is None and sector is None and not use_all:
                return inst_res

            price_res = await self._sync_prices(
                client,
                symbols=symbols,
                sector=sector,
                all_instruments=use_all,
                incremental=incremental,
                include_adjustments=include_adjustments,
                include_share_changes=include_share_changes,
                fail_fast=fail_fast,
                on_progress=on_progress,
            )
            ct_res = (
                await self._sync_client_types(
                    client,
                    symbols=symbols,
                    sector=sector,
                    all_instruments=use_all,
                    incremental=incremental,
                    fail_fast=fail_fast,
                    on_progress=on_progress,
                )
                if include_client_types
                else SyncResult()
            )
            merged_errors = {**price_res.errors, **ct_res.errors}
            return replace(
                price_res,
                sectors=inst_res.sectors,
                instruments=inst_res.instruments,
                client_types=ct_res.client_types,
                errors=merged_errors,
            )

        return await self._run_with_client(None, _run_all)


class SyncService:
    """Synchronous facade over ``AsyncSyncService`` using bounded async HTTP concurrency."""

    def __init__(
        self,
        store: StorageBackend,
        client: AsyncTSETMCClient | None = None,
        *,
        max_concurrency: int = 8,
        transport: httpx2.AsyncBaseTransport | None = None,
        **client_kwargs: Any,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        self.store = store
        self._client = client
        self.max_concurrency = max_concurrency
        self._transport = transport
        self._client_kwargs = dict(client_kwargs)

    def _run(self, coro_fn: Callable[[AsyncSyncService], Awaitable[SyncResult]]) -> SyncResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise StorageError(
                "SyncService cannot be called synchronously inside a running event loop; "
                "use AsyncSyncService instead"
            )

        async def _runner() -> SyncResult:
            if self._client is not None:
                svc = AsyncSyncService(
                    self.store,
                    client=self._client,
                    max_concurrency=self.max_concurrency,
                )
                return await coro_fn(svc)
            async with AsyncSyncService(
                self.store,
                max_concurrency=self.max_concurrency,
                transport=self._transport,
                **self._client_kwargs,
            ) as svc:
                return await coro_fn(svc)

        return asyncio.run(_runner())

    def sync_instruments(
        self,
        *,
        on_progress: Callable[[SyncProgress], Any] | None = None,
    ) -> SyncResult:
        """Sync all sectors and instruments in 2 HTTP calls."""
        return self._run(lambda svc: svc.sync_instruments(on_progress=on_progress))

    def sync_prices(
        self,
        symbols: Sequence[str | int] | None = None,
        *,
        sector: str | None = None,
        all_instruments: bool = False,
        incremental: bool = True,
        overlap_days: int = 0,
        include_adjustments: bool = True,
        include_share_changes: bool = False,
        fail_fast: bool = False,
        on_progress: Callable[[SyncProgress], Any] | None = None,
    ) -> SyncResult:
        """Incrementally sync daily OHLCV prices (and adjustments) for matching targets."""
        return self._run(
            lambda svc: svc.sync_prices(
                symbols=symbols,
                sector=sector,
                all_instruments=all_instruments,
                incremental=incremental,
                overlap_days=overlap_days,
                include_adjustments=include_adjustments,
                include_share_changes=include_share_changes,
                fail_fast=fail_fast,
                on_progress=on_progress,
            )
        )

    def sync_client_types(
        self,
        symbols: Sequence[str | int] | None = None,
        *,
        sector: str | None = None,
        all_instruments: bool = False,
        incremental: bool = True,
        overlap_days: int = 0,
        fail_fast: bool = False,
        on_progress: Callable[[SyncProgress], Any] | None = None,
    ) -> SyncResult:
        """Incrementally sync daily institutional/individual flow for matching targets."""
        return self._run(
            lambda svc: svc.sync_client_types(
                symbols=symbols,
                sector=sector,
                all_instruments=all_instruments,
                incremental=incremental,
                overlap_days=overlap_days,
                fail_fast=fail_fast,
                on_progress=on_progress,
            )
        )

    def sync_all(
        self,
        symbols: Sequence[str | int] | None = None,
        *,
        sector: str | None = None,
        all_instruments: bool = True,
        incremental: bool = True,
        include_client_types: bool = True,
        include_adjustments: bool = True,
        include_share_changes: bool = False,
        fail_fast: bool = False,
        on_progress: Callable[[SyncProgress], Any] | None = None,
    ) -> SyncResult:
        """Sync instruments/sectors followed by prices and optional client-type flow."""
        return self._run(
            lambda svc: svc.sync_all(
                symbols=symbols,
                sector=sector,
                all_instruments=all_instruments,
                incremental=incremental,
                include_client_types=include_client_types,
                include_adjustments=include_adjustments,
                include_share_changes=include_share_changes,
                fail_fast=fail_fast,
                on_progress=on_progress,
            )
        )
