import os

from tehran_stocks import db, models, update_group, get_all_price
from tehran_stocks.download import fill_stock_table


def init_db():
    print("creating database")
    path = os.path.join(db.HOME_PATH, db.TSE_FOLDER)

    if "tse" not in os.listdir(db.HOME_PATH):
        print("making package folder...")
        print("Includes: config.yml and stocks.db  if you are using sqlite.")
        print("you can change config.yml to your needs.")
        try:
            os.mkdir(path)
        except FileExistsError:
            print("folder already exists")
    models.create()
    print(f"DataBase created in: {path}")


def fill_db():
    print("downloading stock name and details from TSETMC")
    print("may take few minutes")

    fill_stock_table()
    print("Stock table is available now, example:")
    print("from tehran_stocks import Stocks")
    print('stock =Stocks.query.filter_by(name="کگل").first()')

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
