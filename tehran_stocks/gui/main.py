import asyncio
import io
import streamlit as st
from tehran_stocks.config.engine import get_session
from tehran_stocks.models import Instrument, InstrumentPrice
from tehran_stocks.initializer import get_all_price, get_instruments
import contextlib

""" 
# Tehran Stocks Manager
"""
session = get_session()
total_instruments = session.query(Instrument).count()
total_prices = session.query(InstrumentPrice).count()

st.write(f"Total Instruments: {total_instruments}")
st.write(f"Total Prices: {total_prices}")

st.write("## Update Prices")


class StreamlitPrintStream:
    def __init__(self):
        self.output = io.StringIO()

    def write(self, text):
        self.output.write(text)
        st.text(text)

    def flush(self):
        pass


if st.button("Update Prices"):
    with st.echo(), contextlib.redirect_stdout(StreamlitPrintStream()):
        st.write("Updating Prices...")
        asyncio.run(get_all_price())

        # print("Updating Prices.. in print.")
        st.write("Done!")

# st.write("## Update Instruments")
if st.button("Update Instruments"):
    with st.echo(), contextlib.redirect_stdout(StreamlitPrintStream()):
        st.write("Updating Instruments...")
        asyncio.run(get_instruments())
        st.write("Done!")
