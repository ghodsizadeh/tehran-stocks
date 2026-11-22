import os
import sys

from sqlalchemy import inspect

import tehran_stocks.config as db
from tehran_stocks.download import (
    get_all_price,
    get_stock_detail,
    get_stock_groups,
    get_stock_ids,
    update_group,
    update_stock_price,
)
from tehran_stocks.models import StockPrice, Stocks, get_asset

from .initializer import init_db, fill_db


def db_is_empty():
    try:
        return not inspect(db.engine).has_table("stocks")
    except Exception:
        return True


def should_fill_db():
    if os.environ.get("TEHRAN_STOCKS_AUTO_FILL", "1") != "1":
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return sys.stdin.isatty()


if db_is_empty():
    print("No database founded.")
    init_db()
    if should_fill_db():
        fill_db()
