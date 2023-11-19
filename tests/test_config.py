import os

from pytest_mock import MockFixture
from tehran_stocks.config.config_file import (
    HOME_PATH,
    TSE_FOLDER,
    create_config,
    create_tse_folder,
)
from tehran_stocks.config.engine import create_engine_uri
import yaml

# path os.remove


def test_create_engine_uri_sqlite():
    database_config = {"engine": "sqlite", "path": "/path/to/database.db"}
    expected_uri = "sqlite:////path/to/database.db"
    assert create_engine_uri(database_config) == expected_uri


def test_create_engine_uri_postgres():
    database_config = {
        "engine": "postgres",
        "host": "localhost",
        "port": "5432",
        "database": "test_db",
        "user": "test_user",
        "password": "test_password",
    }
    expected_uri = "postgres://test_user:test_password@localhost:5432/test_db"
    assert create_engine_uri(database_config) == expected_uri


def test_create_engine_uri_sqlite_default_path():
    database_config = {"engine": "sqlite"}
    expected_uri = f"sqlite:///{HOME_PATH}/{TSE_FOLDER}/tse_data.db"
    assert create_engine_uri(database_config) == expected_uri


def test_create_engine_uri_no_engine():
    database_config = {
        "host": "localhost",
        "port": "5432",
        "database": "test_db",
        "user": "test_user",
        "password": "test_password",
    }
    expected_uri = f"sqlite:///{HOME_PATH}/{TSE_FOLDER}/test_db.db"
    assert create_engine_uri(database_config) == expected_uri


def test_create_tse_folder_exists(mocker: MockFixture):
    mocker.patch("os.path.join", return_value=HOME_PATH)
    mocker.patch("os.mkdir", side_effect=FileExistsError)
    mocker.patch("os.path.exists", return_value=True)
    assert create_tse_folder() is False
    os.mkdir.assert_called_once_with(HOME_PATH)  # type: ignore


def test_create_tse_folder_not_exists(mocker):
    mocker.patch("os.path.join", return_value=HOME_PATH)
    mocker.patch("os.mkdir")
    mocker.patch("os.path.exists", return_value=False)

    assert create_tse_folder() is True

    os.mkdir.assert_called_once_with(HOME_PATH)


def test_create_config_exists(mocker: MockFixture):
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("__main__.open", mocker.mock_open())
    mocker.patch("yaml.full_load")
    mocker.patch("yaml.dump")

    create_config()

    yaml.dump.assert_not_called()  # type: ignore


def test_create_config_not_exists(mocker):
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("__main__.open", mocker.mock_open())
    mocker.patch("yaml.full_load")
    mocker.patch("yaml.dump")

    create_config()

    yaml.dump.assert_called()
