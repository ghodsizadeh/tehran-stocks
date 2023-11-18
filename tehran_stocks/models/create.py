import tehran_stocks.config as db
from .instrument import Instrument
from .instrument_price import InstrumenPrice


def create_database():
    Instrument.__table__.create(db.config_file)
    InstrumenPrice.__table__.create(db.config_file)
