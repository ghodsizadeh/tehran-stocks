import os
import tehran_stocks.config as db
import tehran_stocks.models as models


def init_db():
    print("creating database")
    path = os.path.join(db.home, "tse")

    if not "tse" in os.listdir(db.home):
        print("making database folder ...")
        os.mkdir(path)
    models.create()
    print(f"DataBase created in: {path}")
