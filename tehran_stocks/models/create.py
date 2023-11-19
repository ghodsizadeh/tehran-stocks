from .instrument import Instrument
from .instrument_price import InstrumentPrice


def create_database(engine):
    Instrument.__table__.create(engine)
    InstrumentPrice.__table__.create(engine)
