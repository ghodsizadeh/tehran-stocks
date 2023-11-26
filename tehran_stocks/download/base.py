from typing import Dict
import aiohttp

from traitlets import Any


BASE_URL = "http://old.tsetmc.com"
NEW_BASE_URL = "http://www.tsetmc.com"
CDN_URL = "http://cdn.tsetmc.com"


class FetchMixin:
    def __init__(self) -> None:
        self.session = None
        self.base_url = NEW_BASE_URL
        self.old_base_url = BASE_URL
        self.cdn_url = CDN_URL
        self.headers = {
            "Origin": "http://www.tsetmc.com",
            "Pragma": "no-cache",
            "Referer": "http://www.tsetmc.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        }

    async def _fetch_raw(self, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    raise Exception(
                        f"Error fetching {url}: response code {resp.status}"
                    )
                res: str = await resp.text()
                return res

    async def _fetch(self, url: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    raise Exception(
                        f"Error fetching {url}: response code {resp.status}"
                    )
                res: Dict[str, Any] = await resp.json()
            return res
