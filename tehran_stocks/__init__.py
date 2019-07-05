import tehran_stocks.config as db
import tehran_stocks.models as models
import tehran_stocks.download as downloader
from .initializer import init_db
import os


if not os.path.isfile(db.db_path):
    print("No database founded.")
    init_db()
