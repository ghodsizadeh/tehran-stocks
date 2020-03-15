from setuptools import setup, find_packages


# read the contents of your README file
from os import path

THISDIRECTORY = path.abspath(path.dirname(__file__))
with open(path.join(THISDIRECTORY, "README.md")) as f:
    LONGDESC = f.read()

setup(
    name="tehran-stocks",
    version="0.7.1",
    description="Data Downloader for Tehran stock market",
    url="http://github.com/ghodsizdeh/tehran-stocks",
    author="Mehdi Ghodsizadeh",
    author_email="mehdi.ghodsizadeh@gmail.com",
    license="MIT",
    long_description=LONGDESC,
    long_description_content_type="text/markdown",
    package_dir={"": "src"},
    packages=[
        "tehran_stocks",
        "tehran_stocks.download",
        "tehran_stocks.models",
        "tehran_stocks.config",
    ],
    install_requires=["wheel", "pandas", "sqlalchemy", "requests", "jdatetime"],
    zip_safe=False,
    python_requires=">=3.6",
    scripts=["bin/ts-get", "bin/ts-get.bat"],
    include_package_data=True,
)
