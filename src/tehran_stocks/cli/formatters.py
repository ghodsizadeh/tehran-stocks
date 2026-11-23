"""Shared Rich table, JSON, CSV, and stderr error helpers for the ``tse`` CLI."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
import csv
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum
import io
import json
import math
import sys
from typing import Any, Iterator, Literal, NoReturn

from rich.console import Console
from rich.table import Table
from rich.text import Text
import typer

from tehran_stocks.exceptions import (
    InstrumentNotFoundError,
    RateLimitError,
    StorageError,
    TSETMCError,
    TehranStocksError,
)


class OutputFormat(str, Enum):
    """Supported CLI output serialization formats."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"


EXIT_CODE_MAP: dict[type[BaseException], int] = {
    InstrumentNotFoundError: 3,
    RateLimitError: 4,
    TSETMCError: 5,
    StorageError: 6,
    TehranStocksError: 1,
    ValueError: 2,
}


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    """Declarative column definition for tabular and CSV output."""

    key: str
    header: str
    justify: Literal["default", "left", "center", "right", "full"] = "left"
    style: str = ""
    formatter: Callable[[Any], str] | None = None
    no_wrap: bool = False


def resolve_output_format(fmt: OutputFormat, as_json: bool) -> OutputFormat:
    """Resolve effective output format when ``--json`` shortcut flag is set."""
    return OutputFormat.JSON if as_json else fmt


def get_stdout_console() -> Console:
    """Create a Rich console bound dynamically to the current ``sys.stdout``."""
    return Console(file=sys.stdout)


def get_stderr_console() -> Console:
    """Create a Rich console bound dynamically to the current ``sys.stderr``."""
    return Console(file=sys.stderr, stderr=True)


def exit_code_for_error(exc: BaseException) -> int:
    """Map domain and validation exceptions to deterministic non-zero exit codes."""
    for cls in type(exc).__mro__:
        if cls in EXIT_CODE_MAP:
            return EXIT_CODE_MAP[cls]
    return 1


def print_error(message: str | BaseException, *, label: str | None = None) -> None:
    """Print a clean, markup-safe error message to ``stderr``."""
    prefix = label or (type(message).__name__ if isinstance(message, BaseException) else "Error")
    text = str(message)
    get_stderr_console().print(
        f"{prefix}: {text}",
        style="bold red",
        highlight=False,
        markup=False,
    )


def fail_with_error(exc: BaseException) -> NoReturn:
    """Print ``exc`` cleanly to ``stderr`` and exit with its mapped non-zero code."""
    print_error(exc)
    raise typer.Exit(code=exit_code_for_error(exc))


@contextmanager
def cli_error_boundary() -> Iterator[None]:
    """Convert domain and argument-validation errors into clean ``stderr`` exits."""
    try:
        yield
    except (TehranStocksError, ValueError) as exc:
        fail_with_error(exc)


def to_plain_value(value: Any) -> Any:
    """Recursively convert domain models, dates, and enums to JSON-safe Python values."""
    if value is None:
        return None
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return to_plain_value(value.to_dict())
    if is_dataclass(value) and not isinstance(value, type):
        return to_plain_value(asdict(value))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): to_plain_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def fmt_text(value: Any) -> str:
    """Format a scalar text or identifier cell without numeric punctuation."""
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def fmt_int(value: Any) -> str:
    """Format an integer quantity with thousands separators."""
    if value is None or value == "":
        return "-"
    return f"{int(value):,}"


def fmt_number(value: Any) -> str:
    """Format a price or numeric value, omitting ``.00`` for whole numbers."""
    if value is None or value == "":
        return "-"
    num = float(value)
    if not math.isfinite(num):
        return "-"
    if num.is_integer():
        return f"{int(num):,}"
    return f"{num:,.2f}"


def fmt_float(value: Any, decimals: int = 2) -> str:
    """Format a floating-point number with fixed decimal precision."""
    if value is None or value == "":
        return "-"
    num = float(value)
    if not math.isfinite(num):
        return "-"
    return f"{num:,.{decimals}f}"


def fmt_pct(value: Any, *, signed: bool = True) -> str:
    """Format a percentage value."""
    if value is None or value == "":
        return "-"
    num = float(value)
    if not math.isfinite(num):
        return "-"
    return f"{num:+.2f}%" if signed else f"{num:.2f}%"


def _csv_cell(value: Any) -> Any:
    plain = to_plain_value(value)
    if plain is None:
        return ""
    if isinstance(plain, (list, dict)):
        return json.dumps(plain, ensure_ascii=False)
    return plain


def emit_json(data: Any) -> None:
    """Write formatted JSON directly to ``sys.stdout`` with UTF-8 Persian preservation."""
    payload = to_plain_value(data)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()


def emit_csv(
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[str] | None = None,
) -> None:
    """Write RFC-4180 CSV rows directly to ``sys.stdout``."""
    fieldnames = list(columns) if columns is not None else (list(rows[0].keys()) if rows else [])
    if not fieldnames:
        return

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_cell(row.get(field)) for field in fieldnames})

    sys.stdout.write(buffer.getvalue())
    sys.stdout.flush()


def emit_table(
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[ColumnSpec],
    *,
    title: str | None = None,
    caption: str | None = None,
    empty_message: str = "No results found.",
) -> None:
    """Render rows as a Rich table on ``sys.stdout``."""
    console = get_stdout_console()
    if not rows:
        console.print(Text(empty_message, style="dim"))
        return

    table = Table(
        title=title,
        caption=caption,
        show_header=True,
        header_style="bold cyan",
    )
    for col in columns:
        table.add_column(
            col.header,
            justify=col.justify,
            style=col.style or None,
            no_wrap=col.no_wrap,
        )

    for row in rows:
        rendered_cells: list[Text] = []
        for col in columns:
            raw = row.get(col.key)
            formatted = col.formatter(raw) if col.formatter is not None else fmt_text(raw)
            rendered_cells.append(Text(formatted))
        table.add_row(*rendered_cells)

    console.print(table)


def emit_kv_table(
    record: Mapping[str, Any],
    *,
    title: str | None = None,
    labels: Mapping[str, str] | None = None,
    formatters: Mapping[str, Callable[[Any], str]] | None = None,
) -> None:
    """Render a single key-value record as a two-column Rich table."""
    console = get_stdout_console()
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    for key, value in record.items():
        field_label = labels.get(key, key) if labels else str(key)
        fmt_fn = formatters.get(key, fmt_text) if formatters else fmt_text
        table.add_row(Text(field_label), Text(fmt_fn(to_plain_value(value))))

    console.print(table)


def output_records(
    rows: Sequence[Mapping[str, Any]],
    *,
    fmt: OutputFormat,
    columns: Sequence[ColumnSpec],
    title: str | None = None,
    caption: str | None = None,
    json_data: Any = None,
    empty_message: str = "No results found.",
) -> None:
    """Emit a sequence of records in the requested ``table``, ``json``, or ``csv`` format."""
    if fmt is OutputFormat.JSON:
        emit_json(json_data if json_data is not None else list(rows))
    elif fmt is OutputFormat.CSV:
        emit_csv(rows, columns=[col.key for col in columns])
    else:
        emit_table(
            rows,
            columns,
            title=title,
            caption=caption,
            empty_message=empty_message,
        )


def output_record(
    record: Mapping[str, Any],
    *,
    fmt: OutputFormat,
    title: str | None = None,
    labels: Mapping[str, str] | None = None,
    formatters: Mapping[str, Callable[[Any], str]] | None = None,
    json_data: Any = None,
) -> None:
    """Emit a single mapping record in the requested ``table``, ``json``, or ``csv`` format."""
    if fmt is OutputFormat.JSON:
        emit_json(json_data if json_data is not None else record)
    elif fmt is OutputFormat.CSV:
        emit_csv([record], columns=list(record.keys()))
    else:
        emit_kv_table(record, title=title, labels=labels, formatters=formatters)
