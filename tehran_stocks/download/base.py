import asyncio
from typing import Dict
import aiohttp

from traitlets import Any


BASE_URL = "http://old.tsetmc.com"
NEW_BASE_URL = "http://www.tsetmc.com"
CDN_URL = "http://cdn.tsetmc.com"


class FetchMixin:
    session = None
    base_url = NEW_BASE_URL
    old_base_url = BASE_URL
    cdn_url = CDN_URL
    headers = {
        "Origin": "http://www.tsetmc.com",
        "Pragma": "no-cache",
        "Referer": "http://www.tsetmc.com/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    }

    @classmethod
    async def _fetch_raw(cls, url: str, retries: int = 3) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=cls.headers) as resp:
                if resp.status != 200:
                    retries -= 1
                    if retries > 0:
                        return await cls._fetch_raw(url, retries)
                    raise Exception(
                        f"Error fetching {url}: response code {resp.status}"
                    )
                res: str = await resp.text()
            return res

    @classmethod
    async def _fetch(cls, url: str, retries: int = 3) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=cls.headers) as resp:
                if resp.status != 200:
                    retries -= 1
                    if retries > 0:
                        await asyncio.sleep(0.1)
                        return await cls._fetch(url, retries)
                    raise Exception(
                        f"Error fetching {url}: response code {resp.status}"
                    )
                res: Dict[str, Any] = await resp.json()
            return res
