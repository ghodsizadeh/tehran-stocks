# Tehran Stock Market

[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
![PyPI - Downloads](https://img.shields.io/pypi/dw/tehran_stocks.svg?color=blue)
[![PyPI version](https://badge.fury.io/py/tehran-stocks.svg)](https://badge.fury.io/py/tehran-stocks)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)

<!-- ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/tehran-stocks.svg) -->

A python package that helps to access TCCIM stock price history, Using OOP Interface

## Features

- Download All stocks prices
- Download prices from a group (i.e ETFs or cars, etc.)
- Download Price history of one specific Stock
- After first setup available offline.
- CommandLine Interface
- Export data to csv, excel or Stata(dta)
- Compatible with `sqlalchemy`
- Compatible with `PANDAS`
- Based on light `sqlite`

## 0 - Install

```bash
pip install tehran_stocks_ng
```

## 1- Initialization

For first use you need initialize the database

### 1-1 Command line

```bash
ts-get init  # Set up to sqlite database
```

### 1-2 Python

```python
import tehran_stocks
# On first import package initialize itself
```

During initialization you will prompt for downloading all prices. if you answer yes it will download all prices, otherwise you can download data

## 2- Download and Update prices

### 2-1 Command line

```bash
ts-get update # update  all price , or download all if no price exist
ts-get  group 34 ## 34 is the code for car's group.
ts-get get_groups ## get group name and group codes
```

### 2-2 Python

```python
from tehran_stocks import get_all_price, Stocks, update_group

get_all_price() # download and(or) update all prices

update_group(34) #download and(or) update Stocks in groupCode = 34 (Cars)

Stocks.get_group() # to see list of group codes
```

## 3- Access Data

To access data you can use `Stocks` which is an customized `sqlalchemy` object, which helps you to find prices on an easy way.

### 3-1 Search Stocks

```python
from tehran_stocks import Stocks, db

# You can use query to find stocks
stock = Stocks.query.filter_by(name='كگل').first() #find by symbol(نماد)

stock = Stocks.query.filter_by(code='35700344742885862').first() # find by code on tsetmc url

stock = Stocks.query.filter(Stocks.title.like('%گل گهر%')).first() # Search by title

stock_list = Stocks.query.filter_by(group_code =34).all() # find all Stocks in Khodro

stock_list = Stocks.query.filter(Stocks.group_code.in_([13,34])).all() # all stocks in khodro and felezat


## (Advanced)or run sql query using orm or raw sql
db.session.query(Stocks.group_code, Stocks.group_name).group_by(Stocks.group_code).all()

db.session.execute('select group_code , group_name from stocks group by group_name').fetchall()
```

Now easily access stock price and do whatever you want with `pandas` dataframes:

```python
# use data as a pandas dataframe
>>> stock.df #
      id               code        ticker  dtyyyymmdd    first     high      low    close        value      vol  openint per     open     last       date
0  22491  35700344742885862  Gol-E-Gohar.    20040829  12000.0  12021.0  12000.0  12000.0  18841605000  1570000     2708   D  12000.0  12000.0 2004-08-29

>>> stock.summary()
Start date: 20040829
End date: 20190714
Total days: 2987

>>> stock.update()
# update stock price history

# Export to your preferred format
>>> stock.df.to_csv('price.csv')
>>> stock.df.to_excel('price.xlsx')
>>> stock.df.to_stata('price.dta')

```

## Todo

- [x] Create Database
- [x] Download Data
- [x] CommandLine Support
- [ ] Jalali Support
