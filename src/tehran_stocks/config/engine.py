from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import sessionmaker
from sqlalchemy import *
from pathlib import Path
import os
import sqlite3
import logging
import yaml


HOME_PATH = str(Path.home())
TSE_FOLDER = ".tse"
CONFIG_PATH = os.path.join(HOME_PATH, TSE_FOLDER) + "/" + "config.yml"

if not os.path.exists(CONFIG_PATH):
    # create config.yml from config.deafult.yml
    with open(os.path.join(os.path.dirname(__file__), "config.default.yml"), "r") as f:
        config = yaml.full_load(f)

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f)


with open(CONFIG_PATH, "r") as f:
    config = yaml.full_load(f)

defualt_db_path = os.path.join(f"{HOME_PATH}/{TSE_FOLDER}/stocks.db")

db_path = config.get("database").get("path")
if db_path is None:
    db_path = defualt_db_path

default_engine_URI = f"sqlite:///{db_path}"
engine = config.get("database").get("engine")
if engine == "sqlite":
    engine_URI = default_engine_URI
else:
    engine = config.get("database").get("engine")
    host = config.get("database").get("host")
    port = config.get("database").get("port")
    database = config.get("database").get("database")
    user = config.get("database").get("user")
    password = config.get("database").get("password")
    engine_URI = f"{engine}://{user}:{password}@{host}:{port}/{database}"


logging.info(engine_URI)
engine = create_engine(engine_URI)


Session = sessionmaker()
Session.configure(bind=engine)
session = Session()


class ClassProperty(object):
    def __init__(self, fget):
        self.fget = fget

    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)

    def __repr__(self):
        return None


class QueryMixin:
    @ClassProperty
    def query(cls):
        return session.query(cls)

    def display(self):
        data = self.__dict__
        try:
            del data["_sa_instance_state"]
        except:
            pass
        return data


Base = declarative_base(cls=QueryMixin)
