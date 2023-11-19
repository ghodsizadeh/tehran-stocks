"""
This module is uses to manage flow of tehran_stocks package.
It will handle config and database creation and filling.
"""


from tehran_stocks import models, get_all_price
from tehran_stocks.download import fill_stock_table
from tehran_stocks.config import config_file, engine as engine_config
from sqlalchemy import inspect


def create_config():
    """
    Check if config.yml exists in package folder.
    if not, it will create one.
    """
    config_file.create_tse_folder()
    config_file.create_config()


def check_database(engine):
    """
    Check if database exists.
    if not, it will create one.
    """
    if not engine.dialect.has_table(engine, "stocks"):
        print("Database not found")
        print("Creating database...")
        models.create_database(engine)
        print("Done!")


def create_engine():
    database_config = config_file.get_database_config()
    engine_uri = engine_config.create_engine_uri(database_config)
    engine = engine_config.create_engine(engine_uri)
    return engine


def create_database(engine):
    if not inspect(engine).has_table(models.InstrumentPrice.__tablename__):
        print("Database not found")
        print("Creating database...")
        models.create_database(engine)


def fill_db():
    print("downloading stock name and details from TSETMC")
    print("may take few minutes")

    fill_stock_table()
    print("Stock table is available now, example:")
    print("from tehran_stocks import Instrument")
    print('stock =Instrument.query.filter_by(name="کگل").first()')

    a = input("Do you want to download all price? [y,(n)]")
    if a == "y":
        print("Downloading price:")
        get_all_price()
    else:
        print("if  you want download all prices use tehran_stocks.get_all_price() ")
        print("if you want download price history of a specfic stock use: ")
        print("stock.update()")
        print("or use tehran_stocks.update_group(id) ")
        print("For more info go to:")
        print("https://github.com/ghodsizadeh/tehran-stocks")


if __name__ == "__main__":
    create_config()
    engine = create_engine()
    create_database(engine)
    print("Done!")
