import tehran_stocks.config as db
from tehran_stocks.download import (
    get_all_price,
    get_stock_detail,
    get_stock_groups,
    get_stock_ids,
    update_group,
)
from tehran_stocks.models import StockPrice, Instrument, get_asset

from .initializer import init_db, fill_db

__all__ = [
    "get_stock_detail",
    "get_stock_groups",
    "get_stock_ids",
    "get_all_price",
    "update_group",
    "StockPrice",
    "Instrument",
    "get_asset",
]


def db_is_empty():
    try:
        db.session.execute("select * from stocks limit 1;")
        return False
    except:
        return True


if db_is_empty():
    print("No database founded.")
    init_db()
    fill_db()
