import tehran_stocks.config as db
import tehran_stocks.models as models
from .initialier import init_db
import os


if not os.path.isfile(db.engine_path):
    init_db()

