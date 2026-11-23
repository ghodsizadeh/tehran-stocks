"""Domain exceptions for tehran-stocks."""

from __future__ import annotations


class TehranStocksError(Exception):
    """Base exception for all tehran-stocks errors."""


class TSETMCError(TehranStocksError):
    """Raised when an HTTP or API request to TSETMC fails."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class RateLimitError(TSETMCError):
    """Raised when TSETMC rejects requests due to rate limiting (HTTP 429)."""

    def __init__(
        self,
        message: str = "TSETMC rate limit exceeded",
        status_code: int | None = 429,
        url: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, url=url)
        self.retry_after = retry_after


class InstrumentNotFoundError(TehranStocksError):
    """Raised when a symbol, ISIN, or insCode cannot be resolved."""

    def __init__(self, query: str = "", message: str | None = None) -> None:
        self.query = query
        super().__init__(message or f"Instrument not found: {query!r}")


class StorageError(TehranStocksError):
    """Raised when local storage initialization, query, or sync fails."""
