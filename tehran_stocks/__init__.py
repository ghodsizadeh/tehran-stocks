import tehran_stocks.config as db
from tehran_stocks.download import (
    get_all_price,
    get_stock_detail,
    get_stock_groups,
    get_stock_ids,
    update_group,
)
from tehran_stocks.models import InstrumentPrice, Instrument

# from .initializer import init_db


__all__ = [
    "get_stock_detail",
    "get_stock_groups",
    "get_stock_ids",
    "get_all_price",
    "update_group",
    "Instrument",
    "InstrumentPrice",
    "init_db",
]


def db_is_empty():
    try:
        db.session.execute("select * from stocks limit 1;")
        return False
    except Exception:
        return True

    # init_db()
    # fill_db()


# if __name__ == "__main__":
#     engine = create_engine_with_config()
#     engine = None
#     Session = sessionmaker(bind=engine)
#     session = Session()
