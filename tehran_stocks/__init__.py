import os

import config as db
from download import (
    get_stock_detail,
    get_stock_groups,
    get_stock_ids,
    update_group,
    update_stock_price,
)
from models import StockPrice, Stocks

from .initializer import init_db

if not os.path.isfile(db.db_path):
    print("No database founded.")
    init_db()
