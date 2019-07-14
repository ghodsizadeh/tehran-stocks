import os

from tehran_stocks import db, models, update_group, get_all_price
from tehran_stocks.download import fill_stock_table


def init_db():
    print("creating database")
    path = os.path.join(db.home, "tse")

    if not "tse" in os.listdir(db.home):
        print("making database folder ...")
        os.mkdir(path)
    models.create()
    print(f"DataBase created in: {path}")


def fill_db():
    print("downloding  stock name and details from tccim")
    print("may take few minutes ")
    fill_stock_table()
    print("Stock table is available now, example:")
    print("from tehran_stocks import Stocks")
    print('stock =Stock.query.filter_by(name="کگل").first()')
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

