import requests
import re
import time
import tehran_stocks.config as db
from tehran_stocks.models import Stocks


def get_stock_ids(group):
    url = "http://www.tsetmc.com/tsev2/data/InstValue.aspx?g={}&t=g&s=0"
    r = requests.get(url.format(group))
    ids = set(re.findall("\d{15,20}", r.text))
    return list(ids)


def get_stock_groups():
    r = requests.get("http://www.tsetmc.com/Loader.aspx?ParTree=111C1213")
    groups = re.findall("\d{2}", r.text)
    return groups


def get_stock_detail(stock_id, group_id):
    exist = Stocks.query().filter_by(code=stock_id).first()
    if exist:
        return "exist"
    url = "http://www.tsetmc.com/Loader.aspx?ParTree=151311&i={}".format(stock_id)
    r = requests.get(url)
    stock = {"code": stock_id}
    stock["group_name"] = re.findall("LSecVal='([\D]*)',", r.text)[0]
    stock["instId"] = re.findall("InstrumentID='([\w\d]*)',", r.text)[0]
    stock["insCode"] = (
        stock_id if re.findall("InsCode='(\d*)',", r.text)[0] == stock_id else 0
    )
    stock["baseVol"] = float(re.findall("BaseVol=([\.\d]*),", r.text)[0])
    try:
        stock["name"] = re.findall("LVal18AFC='([\D]*)',", r.text)[0]
    except:
        return
    try:
        stock["title"] = re.findall("Title='([\D]*)',", r.text)[0]
    except:
        return
    try:
        stock["sectorPe"] = float(re.findall("SectorPE='([\.\d]*)',", r.text)[0])
    except:
        stock["sectorPe"] = None
    try:
        stock["shareCount"] = float(re.findall("ZTitad=([\.\d]*),", r.text)[0])
    except:
        stock["shareCount"] = None

    try:
        stock["estimatedEps"] = float(
            re.findall("EstimatedEPS='([\.\d]*)',", r.text)[0]
        )
    except:
        stock["estimatedEps"] = None
    stock["group_code"] = group_id
    db.session.add(Stocks(**stock))
    try:
        db.session.commit()
    except:
        print(f"stock with code {stock_id} exist")
        db.session.rollback()
    return stock


def fill_stock_table():
    print("Downloading group ids...")
    groups = sorted(get_stock_groups())
    for i, group in enumerate(groups):
        stocks = get_stock_ids(group)
        _ = [get_stock_detail(s, int(group)) for s in stocks]
        print(
            f"downloading group: {group}, changes: {(i+1)/len(groups)*100:.1f}% completed",
            end="\r",
        )

    print("Add all groups, you can download stock price by following codes")
    print("from tehran_stocks import downloader")
    print(" downloader.download_all() # for downloading all data")
    print("downloader.download_group(group_id) # to download specefic group data")
    print("downloader.download_stock(stock) to downloand stock specefic")

