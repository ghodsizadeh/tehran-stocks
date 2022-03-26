import re
import time
from jdatetime import date as jdate
from datetime import datetime

import pandas as pd
import requests
import io

import tehran_stocks.config as db
from tehran_stocks.models import StockPrice, Stocks


def convert_to_shamsi(date):
    date = str(date)
    return jdate.fromgregorian(
        day=int(date[-2:]), month=int(date[4:6]), year=int(date[:4])
    ).strftime("%Y/%m/%d")


def update_stock_price(code: str):
    """
    Update (or download for the first time) Stock prices


    params:
    ----------------
    code: str or intege

    example
    ----------------
    `update_stock_price('44891482026867833') #Done`
    or use inside Stock object
    ```
    from tehran_stocks.models import Stocks
    stock = Stocks.query.first()
    stock.update() #Done
    """
    try:
        now = datetime.now().strftime("%Y%m%d")
        try:
            max_date_query = (
                f"select max(dtyyyymmdd) as date from stock_price where code = '{code}'"
            )
            max_date = pd.read_sql(max_date_query, db.engine)
            last_date = max_date.date.iat[0]
        except Exception as e:
            last_date = None
        try:
            if last_date is None:  # no any record added in database
                url = f"http://www.tsetmc.com/tse/data/Export-txt.aspx?a=InsTrade&InsCode={code}&DateFrom=20000101&DateTo={now}&b=0"
            elif str(last_date) < now:  # need to updata new price data
                url = f"http://www.tsetmc.com/tse/data/Export-txt.aspx?a=InsTrade&InsCode={code}&DateFrom={str(last_date)}&DateTo={now}&b=0"
            else:  # The price data for this code is updateed
                return
        except Exception as e:
            print(f"Error on formating price:{str(e)}")

        s = requests.get(url).content
        df = pd.read_csv(io.StringIO(s.decode("utf-8")))
        df.columns = [i[1:-1].lower() for i in df.columns]
        df["code"] = code
        df["date_shamsi"] = ""

        df["date_shamsi"] = df["dtyyyymmdd"].apply(convert_to_shamsi)
        try:
            q = f"select dtyyyymmdd as date from stock_price where code = '{code}'"
            temp = pd.read_sql(q, db.engine)
            df = df[~df.dtyyyymmdd.isin(temp.date)]
        except:
            pass
        df.to_sql("stock_price", db.engine, if_exists="append", index=False)
        return True, code

    except Exception as e:
        print("here")
        return e, code


def update_group(code):
    """
    Update and download data of all stocks in  a group.\n

    `Warning: Stock table should be updated`
    """
    stocks = db.session.query(Stocks.code).filter_by(group_code=code).all()
    if not stocks:
        print("Make sure group has some entity on Stocks")
        return
    for i, stock in enumerate(stocks):
        update_stock_price(stock[0])
        print(f"group progress: {100*(i+1)/len(stocks):.1f}%", end="\r")


def get_all_price():
    codes = db.session.query(db.distinct(Stocks.group_code)).all()
    for i, code in enumerate(codes):
        print(
            f"                         total progress: {100*(i+1)/len(codes):.2f}%",
            end="\r",
        )
        update_group(code[0])

    print("Download Finished.")
