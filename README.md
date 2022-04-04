# Tehran Stock Market بورس تهران در پایتون

[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
![PyPI - Downloads](https://img.shields.io/pypi/dw/tehran_stocks.svg?color=blue)
![PyPI - Downloads](https://img.shields.io/pypi/dm/tehran_stocks.svg?color=blue)
[![PyPI version](https://badge.fury.io/py/tehran-stocks.svg)](https://badge.fury.io/py/tehran-stocks)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/tehran-stocks.svg)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ghodsizadeh/tehran-stocks/blob/master/Example/Read_Data.ipynb)

A python package that helps to access TSETMC stock price history, Using OOP Interface

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

---

## Table of Contents

<!-- TOC orderedlist:true -->

- [1. Tehran Stock Market بورس تهران در پایتون](#1-tehran-stock-market-%D8%A8%D9%88%D8%B1%D8%B3-%D8%AA%D9%87%D8%B1%D8%A7%D9%86-%D8%AF%D8%B1-%D9%BE%D8%A7%DB%8C%D8%AA%D9%88%D9%86)
  - [1.1. Features](#11-features)
  - [1.2. Table of Contents](#12-table-of-contents)
- [2. Usage](#2-usage)
  - [2.1. - Install](#21---install)
  - [2.2. - Initialization](#22---initialization)
    - [2.2.1. -1 Command line](#221--1-command-line)
    - [2.2.2. -2 Python](#222--2-python)
  - [2.3. - Download and Update prices](#23---download-and-update-prices)
    - [2.3.1. -1 Command line](#231--1-command-line)
    - [2.3.2. -2 Python](#232--2-python)
  - [2.4. - Access Data](#24---access-data)
    - [2.4.1. -1 Search Stocks](#241--1-search-stocks)
    - [2.4.2. -2 Get Instant price and more details:](#242--2-get-instant-price-and-more-details)
  - [2.5. - Custom Database](#25---custom-database)
  - [2.6. Todo](#26-todo)
- [3. Support❤️](#3-support)

<!-- /TOC -->

# Usage

## 0 - Install

```bash
pip install tehran_stocks
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
>>> stock.df#
      id               code        ticker  dtyyyymmdd    first     high      low    close        value      vol  openint per     open     last       date
0  22491  35700344742885862  Gol-E-Gohar.    20040829  12000.0  12021.0  12000.0  12000.0  18841605000  1570000     2708   D  12000.0  12000.0 2004-08-29

>>> stock.summary()
Start date: 2004/08/29
End date: 2019/07/14
Total days: 2987

>>> stock.update()
# update stock price history

# Export to your preferred format
>>> stock.df.to_csv('price.csv')
>>> stock.df.to_excel('price.xlsx')
>>> stock.df.to_stata('price.dta')

```

### 3-2 Get Instant price and more details:

```python
>>> stock.get_instant_detail()
{'time': '12:29:57',
 'last_price': '12950',
 'last_close': '13060',
 'last_high': '13300',
 'last_low': '13130',
 'last_open': '13330',
 'trade_count': '12760',
 'trade_volume': '1140',
 'trade_value': '4671236',
 'market_cap': '60715047900',
 'date_string': '20220404',
 'time_string': '122957'}

# get change in share count
>>> stock.get_shares_history()

date	new_shares	old_shares	gdate
0	1400-12-08 00:00:00	200.000 B	100.000 B	2022-02-27
1	1400-04-20 00:00:00	100.000 B	74.400 B	2021-07-11

# get change in price ~ dividend, split, etc.
>> stock.get_dividend()
date	after	before	dividend	gdate
0	1400-04-16 00:00:00	18770	20070	1300	2021-07-07
1	1399-04-18 00:00:00	16350	17250	900	2020-07-08
)
```

## 4- Custom Database

You can change the default database by updating the config file on:

```bash
~/.tse/config.yml #unix MacOS/Linux
C:\Users\User\{USERNAME}\.tse\config.yml #Windows
```

Custom Config for postgresql (you may need to install `pyscopg2`):

```yaml
database:
  database: stocks
  engine: postgresql
  host: localhost
  password: password
  port: 5432
  user: postgres
```

## Todo

- [x] Create Database
- [x] Download Data
- [x] CommandLine Support
- [x] Jalali Support
- [x] Instant Data
- [x] Custom database

# Support❤️

- If you like this package you can buy me a cup of coffee ☕️.
  - [IDPAY](https://idpay.ir/ghodsizadeh)
  - ![Keybase BTC](https://img.shields.io/keybase/btc/mghodsizadeh)
- Subscribe and share my youtube channel [![Youtube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtube.com/channel/UCF3v_GwH3Jg2c-V3hRwmcbg)
