"""MCP server entrypoint and configuration helpers for tehran-stocks."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import logging
import os
from pathlib import Path
import sys
from typing import Literal

from tehran_stocks.mcp_server.tools import (
    ServerConfig,
    create_server,
    resolve_server_config,
)


def configure_stderr_logging(level: str = "INFO") -> None:
    """Configure Python logging strictly to ``sys.stderr`` so ``stdout`` stays clean."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.basicConfig(
        level=level.upper(),
        handlers=[handler],
        force=True,
    )


def _parse_port(value: str) -> int:
    """Parse and validate a TCP port in 1..65535 for CLI arguments."""
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid int value: {value!r}") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def run_server(
    *,
    db_path: str | Path | None = None,
    transport: Literal["stdio", "streamable-http"] = "stdio",
    timeout: float | None = None,
    proxy: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    log_level: str = "INFO",
) -> None:
    """Configure stderr-only logging, build the ``MCPServer``, and start serving."""
    if not 1 <= port <= 65535:
        raise ValueError(f"port must be between 1 and 65535 (got {port})")
    configure_stderr_logging(log_level)
    config = resolve_server_config(
        db_path=db_path,
        timeout=timeout,
        proxy=proxy,
        transport=transport,
    )
    server = create_server(
        db_path=config.db_path,
        timeout=config.timeout,
        proxy=config.proxy,
        transport=config.transport,
    )
    # Re-apply stderr handler in case MCPServer's internal configure_logging altered handlers.
    configure_stderr_logging(log_level)

    active_transport = config.transport or "stdio"
    if active_transport == "streamable-http":
        server.run(transport="streamable-http", host=host, port=port)
    else:
        server.run(transport="stdio")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tehran-stocks-mcp",
        description="Run the official mcp>=2.0 MCPServer for Tehran Stock Exchange (TSETMC).",
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        default=None,
        help="Optional SQLite path or SQLAlchemy DB URI (falls back to TEHRAN_STOCKS_DB).",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport protocol (default: stdio).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="HTTP request timeout in seconds (falls back to TEHRAN_STOCKS_TIMEOUT or 20.0).",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="Optional HTTP/SOCKS proxy URL (falls back to TEHRAN_STOCKS_PROXY).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for streamable-http transport (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=_parse_port,
        default=8000,
        help="Bind port (1-65535) for streamable-http transport (default: 8000).",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("TEHRAN_STOCKS_LOG_LEVEL", "INFO"),
        help="Logging level written strictly to stderr (default: INFO).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entrypoint for ``tehran-stocks-mcp``."""
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    run_server(
        db_path=args.db_path,
        transport=args.transport,
        timeout=args.timeout,
        proxy=args.proxy,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )


__all__ = [
    "ServerConfig",
    "configure_stderr_logging",
    "create_server",
    "main",
    "resolve_server_config",
    "run_server",
]
