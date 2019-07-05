from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import sessionmaker
from sqlalchemy import *
from pathlib import Path
import os

home = str(Path.home())
if not "tse" in os.listdir(home):
    os.mkdir(os.path.join(home, "tse"))
engine_path = "sqlite:///" + home + "/tse/" + "stocks.db"
engine = create_engine("sqlite:///Stocks.db")

Session = sessionmaker()
Session.configure(bind=engine)
session = Session()


class QueryMixin:
    @classmethod
    def query(cls):
        return session.query(cls)

    def display(self):
        data = self.__dict__
        del data["_sa_instance_state"]
        return data


Base = declarative_base(cls=QueryMixin)
