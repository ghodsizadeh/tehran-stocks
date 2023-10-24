from typing import Dict
import aiohttp

from traitlets import Any


BASE_URL = "http://old.tsetmc.com"
NEW_BASE_URL = "http://www.tsetmc.com"
CDN_URL = "http://cdn.tsetmc.com"


class FetchMixin:
    async def _fetch(self, url: str) -> Dict[str, Any]:
        if self.session is None:
            self.session = aiohttp.ClientSession()
        headers = {
            "Origin": "http://www.tsetmc.com",
            "Pragma": "no-cache",
            "Referer": "http://www.tsetmc.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        }

        async with self.session.get(url, headers=headers) as resp:
            if resp.status != 200:
                raise Exception(f"Error fetching {url}: response code {resp.status}")
            return await resp.json()
