import requests
import re


def get_stock_ids(group):
    url = "http://www.tsetmc.com/tsev2/data/InstValue.aspx?g={}&t=g&s=0"
    r = requests.get(url.format(group))
    ids = set(re.findall("\d{15,20}", r.text))
    return list(ids)


def get_stock_groups():
    r = requests.get("http://www.tsetmc.com/Loader.aspx?ParTree=111C1213")
    groups = re.findall("\d{2}", r.text)
    return groups

