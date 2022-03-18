from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import sessionmaker
from sqlalchemy import *
from pathlib import Path
import os
import sqlite3

home = str(Path.home())
db_path = os.path.join(f'{home}/.tse/stocks.db')
engine_path = f"sqlite:///{db_path}"
creator = lambda: sqlite3.connect(
    "file::memory:?cache=shared", uri=True
)  # Add caching into sqlalchemy
# engine = create_engine(engine_path,creator=creator)
print(engine_path)
engine = create_engine(engine_path)


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
