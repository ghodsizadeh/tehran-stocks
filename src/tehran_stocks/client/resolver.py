"""Symbol, ISIN, and numeric insCode resolution with in-memory TTL caching."""

from __future__ import annotations

from collections.abc import Mapping
import re
import threading
import time
from typing import Any
from urllib.parse import quote

from tehran_stocks.client.transport import AsyncTransport, SyncTransport
from tehran_stocks.exceptions import InstrumentNotFoundError
from tehran_stocks.types.instrument import Instrument
from tehran_stocks.utils.persian import normalize_persian

_ISIN_RE = re.compile(r"^IR[A-Z0-9]{10}$")
_PRIMARY_BOARDS = frozenset({"N1", "N2", "1A", "2A", "5N", "G1", "G2"})


def _flow_rank(flow: int | None) -> int:
    if flow == 1:
        return 4
    if flow == 2:
        return 3
    if flow == 4:
        return 2
    if flow is not None and flow > 0:
        return 1
    return 0


class _BaseResolver:
    """Shared normalization, ranking, and TTL cache helpers for symbol resolution."""

    def __init__(self, *, cache_ttl: float = 3600.0) -> None:
        if cache_ttl < 0:
            raise ValueError("cache_ttl must be >= 0")
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[str, float]] = {}

    @staticmethod
    def _normalize_query(identifier: str | int) -> str:
        return normalize_persian(str(identifier)).strip()

    @staticmethod
    def _search_path(normalized: str) -> str:
        return f"/api/Instrument/GetInstrumentSearch/{quote(normalized, safe='')}"

    @staticmethod
    def _try_direct_ins_code(normalized: str) -> str | None:
        if not normalized:
            return None
        if normalized.isdigit():
            if len(normalized) >= 5 and int(normalized) > 0:
                return normalized
            return None
        return None

    def _cache_get(self, key: str) -> str | None:
        if self.cache_ttl <= 0:
            return None
        entry = self._cache.get(key)
        if entry is None:
            return None
        ins_code, expires_at = entry
        if time.monotonic() >= expires_at:
            self._cache.pop(key, None)
            return None
        return ins_code

    def _cache_set(self, key: str, ins_code: str) -> None:
        if self.cache_ttl <= 0 or not key or not ins_code:
            return
        self._cache[key] = (ins_code, time.monotonic() + self.cache_ttl)

    def clear_cache(self) -> None:
        """Clear all cached symbol-to-insCode resolutions."""
        self._cache.clear()

    @staticmethod
    def _score_candidate(
        raw_row: Mapping[str, Any],
        instrument: Instrument,
        normalized_query: str,
        upper_query: str,
        is_isin: bool,
    ) -> tuple[int, int, int, int, int, int] | None:
        if not instrument.ins_code or instrument.ins_code == "0":
            return None

        exact_isin = (
            instrument.isin.upper() == upper_query
            or instrument.instrument_id.upper() == upper_query
        )
        exact_symbol = instrument.symbol == normalized_query

        if not exact_symbol and not exact_isin:
            if not is_isin:
                return None

        board = str(raw_row.get("cgrValCot") or "").strip().upper()
        last_date = raw_row.get("lastDate")
        has_activity = 1 if (isinstance(last_date, (int, float)) and last_date > 0) else 0
        is_primary_board = 1 if board in _PRIMARY_BOARDS else 0
        has_shares = 1 if instrument.total_shares > 0 else 0

        return (
            1 if (exact_symbol or exact_isin) else 0,
            _flow_rank(instrument.flow),
            is_primary_board,
            has_activity,
            has_shares,
            1 if "ح ." not in instrument.name else 0,
        )

    @classmethod
    def _select_ins_code(
        cls,
        payload: Any,
        raw_query: str,
        normalized_query: str,
    ) -> str:
        if isinstance(payload, Mapping):
            rows = payload.get("instrumentSearch") or []
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []

        if not isinstance(rows, list) or not rows:
            raise InstrumentNotFoundError(raw_query)

        upper_query = normalized_query.upper()
        is_isin = bool(_ISIN_RE.match(upper_query))

        best_score: tuple[int, int, int, int, int, int] | None = None
        best_ins_code: str | None = None

        for row in rows:
            if not isinstance(row, Mapping):
                continue
            instrument = Instrument.from_tsetmc(row)
            score = cls._score_candidate(
                row,
                instrument,
                normalized_query=normalized_query,
                upper_query=upper_query,
                is_isin=is_isin,
            )
            if score is None:
                continue
            if best_score is None or score > best_score:
                best_score = score
                best_ins_code = instrument.ins_code

        if best_ins_code is None:
            raise InstrumentNotFoundError(raw_query)
        return best_ins_code


class SyncResolver(_BaseResolver):
    """Synchronous resolver converting symbols, ISINs, or insCodes to ``insCode``."""

    def __init__(self, transport: SyncTransport, *, cache_ttl: float = 3600.0) -> None:
        super().__init__(cache_ttl=cache_ttl)
        self._transport = transport
        self._lock = threading.Lock()

    def clear_cache(self) -> None:
        with self._lock:
            super().clear_cache()

    def resolve(self, identifier: str | int) -> str:
        """Resolve a Persian/Arabic symbol, ISIN, or numeric insCode into an ``insCode``."""
        raw_query = str(identifier)
        normalized = self._normalize_query(identifier)
        if not normalized or normalized == "0":
            raise InstrumentNotFoundError(raw_query)

        if normalized.isdigit():
            direct = self._try_direct_ins_code(normalized)
            if direct is None:
                raise InstrumentNotFoundError(raw_query)
            return direct

        cache_key = normalized.upper() if _ISIN_RE.match(normalized.upper()) else normalized
        with self._lock:
            cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        payload = self._transport.get_json(self._search_path(normalized))
        ins_code = self._select_ins_code(payload, raw_query=raw_query, normalized_query=normalized)
        with self._lock:
            self._cache_set(cache_key, ins_code)
        return ins_code


class AsyncResolver(_BaseResolver):
    """Asynchronous resolver converting symbols, ISINs, or insCodes to ``insCode``."""

    def __init__(self, transport: AsyncTransport, *, cache_ttl: float = 3600.0) -> None:
        super().__init__(cache_ttl=cache_ttl)
        self._transport = transport

    async def resolve(self, identifier: str | int) -> str:
        """Resolve a Persian/Arabic symbol, ISIN, or numeric insCode into an ``insCode``."""
        raw_query = str(identifier)
        normalized = self._normalize_query(identifier)
        if not normalized or normalized == "0":
            raise InstrumentNotFoundError(raw_query)

        if normalized.isdigit():
            direct = self._try_direct_ins_code(normalized)
            if direct is None:
                raise InstrumentNotFoundError(raw_query)
            return direct

        cache_key = normalized.upper() if _ISIN_RE.match(normalized.upper()) else normalized
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        payload = await self._transport.get_json(self._search_path(normalized))
        ins_code = self._select_ins_code(payload, raw_query=raw_query, normalized_query=normalized)
        self._cache_set(cache_key, ins_code)
        return ins_code
