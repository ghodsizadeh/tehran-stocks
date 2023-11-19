import contextlib
import os
from pathlib import Path
from typing import Dict, Optional

import yaml

HOME_PATH = str(Path.home())
TSE_FOLDER = ".tse"
CONFIG_PATH = f"{os.path.join(HOME_PATH, TSE_FOLDER)}/config.yml"


def create_tse_folder() -> bool:
    # Create the .tse folder if it doesn't exist
    with contextlib.suppress(FileExistsError):
        path = os.path.join(HOME_PATH, TSE_FOLDER)
        os.mkdir(path)
        return True
    return False


def create_config():
    # Create config.yml from config.default.yml
    if not os.path.exists(CONFIG_PATH):
        print("creating ~/.tse/config.yml")
        with open(
            os.path.join(os.path.dirname(__file__), "config.default.yml"), "r"
        ) as f:
            config = yaml.full_load(f)
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(config, f)
        print("config.yml created")


def get_database_config() -> Dict[str, Optional[str]]:
    # Get the database configuration from the config file
    with open(CONFIG_PATH, "r") as f:
        config = yaml.full_load(f)
        if config is None:
            os.remove(CONFIG_PATH)
            print("config.yml was empty, please try again")
        return config.get("database", {})
