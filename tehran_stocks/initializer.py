"""
This module is uses to manage flow of tehran_stocks package.
It will handle config and database creation and filling.
"""


import asyncio
from time import time
from typing import List
from tehran_stocks import models
from tehran_stocks.data.instrument_types import basic_instrument_types
from tehran_stocks.download.names import InstrumentList
from tehran_stocks.download.details import InstrumentDetailAPI
from tehran_stocks.config import config_file, engine as engine_config
from tehran_stocks.config.engine import get_session
from sqlalchemy import inspect
from tqdm import tqdm

from tehran_stocks.schema.details import InstrumentInfo


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


async def fill_db():
    print("Downloading instruments name and details from TSETMC")
    print("may take few minutes")
    t0 = time()

    ins_ids = await InstrumentList.get_ins_codes()
    tasks = []
    for ins_code, ins_id in ins_ids:
        if ins_id[2:4] in basic_instrument_types:
            tasks.append(
                asyncio.create_task(InstrumentDetailAPI(ins_code).get_instrument_info())
            )
    print(f"Creating {len(tasks)} tasks in {time()-t0:.1f} seconds")
    print("Start downloading details, it may take few minutes")
    batch_size = 10
    t0 = time()
    results: List[InstrumentInfo] = []
    for i in tqdm(range(0, len(tasks) // 20, batch_size)):
        # await asyncio.gather(*tasks[i:i+batch_size])
        results += await asyncio.gather(
            *tasks[i : i + batch_size], return_exceptions=True
        )
        tqdm.write(f"{i}/{len(tasks)} completed", end="\r")
    print(f"Done in {time()-t0:.1f} seconds")
    engine = create_engine()
    session = get_session(engine=engine)
    print("Adding to database")
    for result in tqdm(results):
        if isinstance(result, InstrumentInfo):
            item = models.Instrument.from_dict(result)
            session.add(item)
    session.commit()

    # number of failed tasks
    print(f"{len([i for i in results if isinstance(i, Exception)])} failed")

    breakpoint()

    # print("Stock table is available now, example:")
    # print("from tehran_stocks import Instrument")
    # print('stock =Instrument.query.filter_by(name="کگل").first()')

    # a = input("Do you want to download all price? [y,(n)]")
    # if a == "y":
    #     print("Downloading price:")
    #     get_all_price()
    # else:
    #     print("if  you want download all prices use tehran_stocks.get_all_price() ")
    #     print("if you want download price history of a specfic stock use: ")
    #     print("stock.update()")
    #     print("or use tehran_stocks.update_group(id) ")
    #     print("For more info go to:")
    #     print("https://github.com/ghodsizadeh/tehran-stocks")


if __name__ == "__main__":
    create_config()
    engine = create_engine()
    create_database(engine)
    asyncio.run(fill_db())
    print("Done!")
