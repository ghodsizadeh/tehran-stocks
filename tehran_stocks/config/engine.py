import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from .config_file import (
    create_config,
    HOME_PATH,
    TSE_FOLDER,
    create_tse_folder,
    get_database_config,
)


def create_engine_uri(database_config):
    """Create the database URI from the configuration"""
    engine = database_config.get("engine", "sqlite")
    if engine == "sqlite":
        path = database_config.get("path", f"{HOME_PATH}/{TSE_FOLDER}/stocks.db")
        return f"sqlite:///{path}"
    host = database_config.get("host", "localhost")
    port = database_config.get("port", "5432")
    database = database_config.get("database", "stocks")
    user = database_config.get("user", "tse")
    password = database_config.get("password", "tse")
    return f"{engine}://{user}:{password}@{host}:{port}/{database}"


def create_engine_with_config():
    create_tse_folder()
    create_config()
    database_config = get_database_config()
    engine_uri = create_engine_uri(database_config)
    logging.info(engine_uri)
    engine = create_engine(engine_uri)
    return engine


class ClassProperty(object):
    def __init__(self, fget):
        self.fget = fget

    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)

    def __repr__(self):
        return None


engine = create_engine_with_config()


def get_session(engine):
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine)
    session = Session()
    return session


class QueryMixin:
    @ClassProperty
    def query(cls):
        session = get_session(engine)

        return session.query(cls)

    def display(self):
        data = self.__dict__
        try:
            del data["_sa_instance_state"]
        except AttributeError:
            pass
        return data


Base = declarative_base(cls=QueryMixin)
