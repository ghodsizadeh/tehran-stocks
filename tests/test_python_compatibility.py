import os
import subprocess
import sys


def test_import_and_date_conversion_in_fresh_home(tmp_path):
    env = os.environ.copy()
    env.update(HOME=str(tmp_path), TEHRAN_STOCKS_AUTO_FILL="0")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import tehran_stocks; "
            "from tehran_stocks.download.price import convert_to_shamsi; "
            "assert convert_to_shamsi(20240102) == '1402/10/12'",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".tse" / "config.yml").is_file()
