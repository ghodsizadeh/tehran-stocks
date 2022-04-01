from asyncio import tasks
import requests
import re
import time
import tehran_stocks.config as db
from tehran_stocks.models import Stocks


def get_stock_ids():
    url = "http://tsetmc.com/tsev2/data/MarketWatchPlus.aspx"
    r = requests.get(url)
    ids = set(re.findall(r"\d{15,20}", r.text))
    return list(ids)


def get_stock_groups():
    """
    group numbers from tccim, to avoid searching useless group numbers.
    its a helper for other parts of package to collect stock lists.
    """
    r = requests.get("http://www.tsetmc.com/Loader.aspx?ParTree=111C1213")
    return re.findall(r"\d{2}", r.text)


def create_or_update_stock_from_dict(stock_id, stock):
    if exist := Stocks.query.filter_by(code=stock_id).first():
        print(f"stock with code {stock_id} exist")
        exist.shareCount = stock["shareCount"]
        exist.baseVol = stock["baseVol"]
        exist.sectorPe = stock["sectorPe"]
        exist.estimatedEps = stock["estimatedEps"]
    else:
        print(f"creating stock with code {stock_id}")
        db.session.add(Stocks(**stock))


def get_stock_detail(stock_id: str) -> Stocks:
    """
    Dowload stocks detail and save them to the database.
    better not use it alone.
    Its not useful after first setup. ;)


    params
    ----------------
    stockk_id :
        an str of an interger or an integer if not started by 0 whicj represent  the Id
        in tsetmc website i.e. arg i={stock_id} inside  the url
    group_id:
        int: number that represent group of stock

    """

    url = f"http://www.tsetmc.com/Loader.aspx?ParTree=151311&i={stock_id}"
    r = requests.get(url)
    stock = {
        "code": stock_id,
        "instId": re.findall(r"InstrumentID='([\w\d]*)|$',", r.text)[0],
    }

    stock["insCode"] = (
        stock_id if re.findall(r"InsCode='(\d*)',", r.text)[0] == stock_id else 0
    )
    stock["baseVol"] = float(re.findall(r"BaseVol=([\.\d]*),", r.text)[0])
    try:
        stock["name"] = re.findall(r"LVal18AFC='([\D]*)',", r.text)[0]
    except:
        return
    try:
        stock["group_name"] = re.findall(r"LSecVal='([\D]*)',", r.text)[0]
    except:
        return
    try:
        stock["title"] = re.findall(r"Title='([\D]*)',", r.text)[0]
    except:
        return
    try:
        stock["sectorPe"] = float(re.findall(r"SectorPE='([\.\d]*)',", r.text)[0])
    except:
        stock["sectorPe"] = None
    try:
        stock["shareCount"] = float(re.findall(r"ZTitad=([\.\d]*),", r.text)[0])
    except:
        stock["shareCount"] = None

    try:
        stock["estimatedEps"] = float(
            re.findall(r"EstimatedEPS='([\.\d]*)',", r.text)[0]
        )
    except:
        stock["estimatedEps"] = None
    stock["group_code"] = re.findall(r"CSecVal='([\w\d]*)|$',", r.text)[0]
    if stock["name"] == "',DEven='',LSecVal='',CgrValCot='',Flow='',InstrumentID='":
        return False

    create_or_update_stock_from_dict(stock_id, stock)

    try:
        db.session.commit()
    except:
        print(f"stock with code {stock_id} exist")
        db.session.rollback()
    return stock


def fill_stock_table():
    """
    Download Stock Table,
    1- gets groups
    2- gets stock in groups
    3- download stock detail
    4- save them to database
    5- guides you to use the package
    """
    URL = "https://ts-api.ir/api/stocks"
    try:
        print("try Downloading stock table from the package api... ")
        print("visit: https://ts-api.ir/")
        r = requests.get(URL)
        if r.status_code != 200:
            raise ConnectionError("connection error")
        data = r.json()
        stocks = data["stocks"]
        for stock in stocks:
            del stock["id"]
            create_or_update_stock_from_dict(stock["code"], stock)
        db.session.commit()
        return

    except ConnectionError:
        print("fall back to manual mode")
        pass
    except Exception as e:
        print(e)
        pass
    print("Downloading group ids...")
    stocks = get_stock_ids()
    for i, stock in enumerate(stocks):
        get_stock_detail(stock)
        print(
            f"downloading stocks details, changes: {(i+1)/len(stocks)*100:.1f}% completed",
            end="\r",
        )

    print("Add all groups, you can download stock price by following codes")
    print("from tehran_stocks import downloader")
    print(" downloader.download_all() # for downloading all data")
    print("downloader.download_group(group_id) # to download specefic group data")
    print("downloader.download_stock(stock) to downloand stock specefic")
