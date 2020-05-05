import re
import time
from jdatetime import date as jdate
from datetime import datetime

import pandas as pd
import requests

import tehran_stocks.config as db
from tehran_stocks.models import StockPrice, Stocks


def convert_to_shamsi(date):
    date = str(date)
    date_shamsi = jdate.fromgregorian(
        day=int(date[-2:]), month=int(date[4:6]), year=int(date[:4])
    ).strftime("%Y/%m/%d")
    return date_shamsi


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
        q = f"select dtyyyymmdd as date from stock_price where code = {code}"
        temp = pd.read_sql(q, db.engine)
        url = "http://www.tsetmc.com/tsev2/data/Export-txt.aspx?t=i&a=1&b=0&i={}"
        df = pd.read_csv(url.format(code))
        df.columns = [i[1:-1].lower() for i in df.columns]
        df["code"] = code
        df["date_shamsi"] = ""

        # for index, row in df.iterrows():
        #     str_date = str(df.at[index, "dtyyyymmdd"])
        #     date_shamsi = date.fromgregorian(
        #         day=int(str_date[-2:]),
        #         month=int(str_date[4:6]),
        #         year=int(str_date[:4])
        #         ).strftime("%Y/%m/%d")
        #     df.at[index, "date_shamsi"] = date_shamsi
        df["date_shamsi"] = df["dtyyyymmdd"].apply(convert_to_shamsi)

        df = df[~df.dtyyyymmdd.isin(temp.date)]
        # get haghighi-hogughi information for per stock
        url = f"http://www.tsetmc.com/tsev2/data/clienttype.aspx?i={code}"
        names = ["dtyyyymmdd", "T-hagh-kharid", "T-hogh-kharid", "T-hagh-forush", "T-hogh-forush", ",H-hagh-kharid",
                 "H-hogh-kharid", "H-hagh-forush", "H-hogh-forush", "A-hagh-hkarid", "A-hogh-hkarid", "A-hagh-forush",
                 ",A-hogh-forush"]
        hagh_hugh_df = pd.read_csv(url, sep=",", lineterminator=";", names=names)
        df = df.merge(hagh_hugh_df, on=['dtyyyymmdd'])
        df.to_sql("stock_price", db.engine, if_exists="append", index=False)
        return True, code
    except Exception as e:
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
