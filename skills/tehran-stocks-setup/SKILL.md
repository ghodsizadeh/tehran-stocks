---
name: tehran-stocks-setup
description: >-
  Install, configure, and verify tehran-stocks v3.0 across ephemeral CLI execution
  (uvx / tse), Python projects (uv / pip), Model Context Protocol servers (MCPServer
  via tse mcp), Agent Skills (npx skills / tse skill install), and optional local
  databases (SQLiteStore, PostgreSQL, DuckDB via SQLAlchemyStore). Use when setting
  up Tehran Stock Exchange tooling, configuring MCP clients, or migrating from v2.
license: MIT
compatibility: >-
  Requires Python 3.11+ and HTTPS access to cdn.tsetmc.com (plus uv/pip for
  installation and optional [postgres] or [duckdb] extras for external databases).
metadata:
  author: tehran-stocks
  version: "3.0.0"
  repository: "https://github.com/ghodsizadeh/tehran-stocks"
  homepage: "https://ghodsizadeh.github.io/tehran-stocks/"
---

# Tehran Stocks v3.0 Setup

`tehran-stocks` v3.0 is an **on-demand first** toolkit for Tehran Stock Exchange (`cdn.tsetmc.com`) data. Unlike v2, importing `tehran_stocks` creates **zero files, zero databases, and zero interactive prompts**. Everything works live out of the box via a single batteries-included install (`httpx2[http2]`, `pandas`, `jalali-pandas>=1.0.0`, `typer`, `mcp>=2.0`, `sqlalchemy>=2.0`).

## Choose Your Setup Mode

| Goal | Recommended Path | Persistence Needed? |
| :--- | :--- | :--- |
| One-off shell queries or scripts | `uvx --from tehran-stocks tse ...` | No |
| Connect an AI assistant (Claude, Cursor, Codex, Antigravity) | MCP Server (`tse mcp` / `tehran-stocks-mcp`) | Optional (`--db`) |
| Python notebooks, backtesting, `pandas` + `jalali-pandas` | `uv add tehran-stocks` or `pip install tehran-stocks` | Optional (`open_store`) |
| Offline multi-year SQL warehouse / full-market screening | `SQLiteStore` (built-in) or `SQLAlchemyStore` (`[postgres]` / `[duckdb]`) | Yes (opt-in) |
| Install Agent Skills into a project or global agent directory | `npx skills add ghodsizadeh/tehran-stocks` or `tse skill install` | No |

---

## 1. Zero-Install CLI (`uvx`)

Run the `tse` Typer CLI directly without polluting your environment:

```bash
# Canonical uvx invocation (recommended)
uvx --from tehran-stocks tse --help

# Shorthand alias (tehran-stocks script mirrors tse)
uvx tehran-stocks --help

# Verify live TSETMC connectivity (JSON output for agents/scripts)
uvx --from tehran-stocks tse market --json
uvx --from tehran-stocks tse quote کگل --json
```

---

## 2. Python Library Installation

Install the unified package into a Python `>=3.11,<4` environment:

```bash
# With uv (recommended)
uv add tehran-stocks

# With pip
pip install tehran-stocks
```

### Optional External Database Extras

Built-in `SQLiteStore` uses Python's standard library `sqlite3` (WAL mode) and requires **no extras**. Install optional driver extras only when connecting `SQLAlchemyStore` to PostgreSQL or DuckDB:

```bash
# PostgreSQL (installs psycopg[binary]>=3.2)
uv add "tehran-stocks[postgres]"
# or: pip install "tehran-stocks[postgres]"

# DuckDB (installs duckdb>=1.1 and duckdb-engine>=0.13)
uv add "tehran-stocks[duckdb]"
# or: pip install "tehran-stocks[duckdb]"
```

### Verify Python Setup

```bash
python -c "import tehran_stocks as ts; q = ts.quote('کگل'); print(q)"
```

Confirming no side effects: importing `tehran_stocks` should return immediately without creating `~/.tse/` or downloading anything until a method is explicitly called.

---

## 3. Configure the MCP Server (`mcp>=2.0` `MCPServer`)

`tehran-stocks` ships an official `mcp>=2.0` `MCPServer` supporting `stdio` (default) and `streamable-http` transports. Logs are written strictly to `stderr` so `stdout` JSON-RPC stays clean.

### Standard Zero-Install MCP Client Config

Add this to your MCP client configuration (Claude Desktop, Cursor, Windsurf, Codex, Antigravity, etc.):

```json
{
  "mcpServers": {
    "tehran-stocks": {
      "command": "uvx",
      "args": ["--from", "tehran-stocks", "tse", "mcp"]
    }
  }
}
```

Equivalent direct console entrypoint:

```json
{
  "mcpServers": {
    "tehran-stocks": {
      "command": "uvx",
      "args": ["--from", "tehran-stocks", "tehran-stocks-mcp"]
    }
  }
}
```

### MCP Server with Opt-In Local Database

When `--db` (or `TEHRAN_STOCKS_DB`) is configured, the MCP server exposes **12 tools** (the 10 live on-demand tools plus `sync_local_db` and `query_local_db` with read-only SQL enforcement):

```json
{
  "mcpServers": {
    "tehran-stocks": {
      "command": "uvx",
      "args": [
        "--from",
        "tehran-stocks",
        "tse",
        "mcp",
        "--db",
        "/path/to/tse.sqlite"
      ],
      "env": {
        "TEHRAN_STOCKS_TIMEOUT": "30"
      }
    }
  }
}
```

### Server CLI Flags & Environment Variables

| CLI Flag | Environment Variable | Purpose |
| :--- | :--- | :--- |
| `--db` | `TEHRAN_STOCKS_DB` | SQLite file path or SQLAlchemy URI (`sqlite:///...`, `postgresql://...`, `duckdb:///...`) |
| `--transport` | — | Transport mode: `stdio` (default) or `streamable-http` |
| `--timeout` | `TEHRAN_STOCKS_TIMEOUT` | HTTP request timeout in seconds |
| `--proxy` | `TEHRAN_STOCKS_PROXY` | HTTP/SOCKS proxy URL if required by local network |
| `--host` / `--port` | — | Bind host and port when using `--transport streamable-http` |

---

## 4. Optional Local Database Setup (`SQLiteStore` & `SQLAlchemyStore`)

### Pre-Built Full-Market SQLite Snapshot (`data-latest`)

To skip an initial multi-thousand-symbol backfill, download the pre-built SQLite snapshot (~184 MiB `zstd`) from GitHub Releases and top it up incrementally:

```bash
curl -fL https://github.com/ghodsizadeh/tehran-stocks/releases/download/data-latest/tse.sqlite.zst -o tse.sqlite.zst
zstd -d tse.sqlite.zst -o tse.sqlite
tse db status --db ./tse.sqlite
tse db sync --db ./tse.sqlite --incremental --client-type
```

### Via `tse db` CLI

```bash
# 1. Initialize an explicit SQLite database
tse db init --db ./tse.sqlite

# 2. Sync market instruments, sectors, and incremental prices/client-type flows
tse db sync --db ./tse.sqlite --symbols کگل --client-type

# 3. Inspect synced coverage and row counts
tse db status --db ./tse.sqlite

# 4. Run read-only analytical SQL
tse db query --db ./tse.sqlite "SELECT ins_code, symbol, name, sector_code FROM instruments LIMIT 10" --json
```

### Via Python (`open_store` / `SyncService`)

```python
from tehran_stocks.storage import SQLiteStore, SQLAlchemyStore, SyncService, open_store

# Built-in SQLite (WAL mode, zero external deps)
store = open_store("./tse.sqlite")          # returns SQLiteStore
SyncService(store).sync_all(symbols=["کگل"], include_client_types=True)

# Or SQLAlchemyStore for PostgreSQL / DuckDB / MySQL
pg_store = open_store("postgresql://user:pass@localhost:5432/tse")
duck_store = open_store("duckdb:///./tse.duckdb")
```

---

## 5. Install Agent Skills

Install both `tehran-stocks-setup` and `tehran-stocks-analysis` into your agent workspace or global config using either `npx skills` or the bundled Python CLI:

### Option A: `npx skills` (from GitHub)

```bash
# Install into the current project
npx skills add ghodsizadeh/tehran-stocks

# Install specific skills or install globally (-g)
npx skills add ghodsizadeh/tehran-stocks --skill tehran-stocks-setup --skill tehran-stocks-analysis -g
```

### Option B: Bundled Wheel Installer (`tse skill`)

Skills are packaged inside the Python wheel under `tehran_stocks/_skills/`:

```bash
# List bundled skills and inspect packaged path
tse skill list
tse skill path

# Install automatically or target a specific agent harness
tse skill install --target auto --scope project
tse skill install --target claude --scope global
# Supported --target values: auto | claude | cursor | codex | antigravity | agents
# Supported --scope values:  project | global

# Existing installs (directories or npx-skills symlinks) are never replaced by default:
# the command checks every destination first and exits without changing anything.
# Pass --overwrite to replace them (copies are staged, then swapped in atomically).
tse skill install --target claude --scope global --overwrite
```

---

## 6. Migrating from `tehran-stocks` v2 & Troubleshooting

### v2 → v3 Quick Migration Map

| Legacy v2 Pattern (Removed in v3) | Modern v3.0 Replacement |
| :--- | :--- |
| `import tehran_stocks` auto-creating `~/.tse/stocks.db` | Zero side effects; use `open_store(path)` explicitly if persistence is wanted |
| `~/.tse/config.yml` | Explicit connection path/URI passed to `open_store()`, `--db`, or `TEHRAN_STOCKS_DB` |
| `Stocks.query.filter_by(name='كگل').first()` | `ts.search("کگل")` / `ts.quote("کگل")` / `client.instruments.info("کگل")` |
| `ts-get init` / `ts-get update` | `tse db init` / `tse db sync` (or skip DB completely with `tse quote`, `tse history`, etc.) |
| `get_all_price()` / `update_group()` | `SyncService` incremental async sync |

### Common Setup Issues

1. **Persian vs. Arabic `ک`/`ی` characters**: v3.0 normalizes Persian (`ک`, `ی`) and Arabic (`ك`, `ي`) transparently via `normalize_persian()`, so `"کگل"` and `"كگل"` resolve identically.
2. **Slow or blocked connections to `cdn.tsetmc.com`**: Set `--timeout` / `TEHRAN_STOCKS_TIMEOUT` or route via `--proxy` / `TEHRAN_STOCKS_PROXY`. `httpx2` handles HTTP/2, system TLS (`truststore`), and browser `User-Agent` headers automatically (`GET` endpoints only). For a SOCKS proxy, install the optional dependency with `pip install "tehran-stocks[socks]"` or run through `uvx --from "tehran-stocks[socks]" tse ...`.
3. **Missing driver error in `SQLAlchemyStore`**: Install `tehran-stocks[postgres]` or `tehran-stocks[duckdb]` for external database engines; `SQLiteStore` works with zero extras.
