# Contributing

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv sync --locked --python 3.11
uv run --locked --python 3.11 pytest -q tests/test_python_compatibility.py
```

Pull requests run the offline compatibility test on Python 3.11 and 3.12,
validate the distribution metadata, and install and import the built wheel.
The existing downloader tests contact TSETMC; run them separately by manually
starting the **Python CI** workflow with **live_tests** enabled.

## Release checklist

1. Update the version in `pyproject.toml` and run `uv lock` if needed. Commit both files and wait for CI to pass on `master`.
2. Tag the release commit as `v<version>` and push the tag. CI verifies the tag matches the package version and uploads the wheel and source distribution.
3. After the tag checks pass, download the `distributions` artifact and attach both files to the GitHub release. Publish to PyPI using the maintainer's authorized credentials if desired; this workflow does not publish automatically.
