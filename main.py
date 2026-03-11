from playwright.async_api import async_playwright

import pandas as pd
import httpx
from datetime import datetime
from config import WBConfig
import asyncio
import argparse
import os
from tqdm.asyncio import tqdm
from typing import Optional, Tuple
from pydantic import BaseModel, Field

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("query",type=str, help="Search query (Russian)")
    return p.parse_args()

class WBPrice(BaseModel):
    product: int = 0
    basic: int = 0

class WBSize(BaseModel):
    name: str = ""
    wh: int = 0
    price: Optional[WBPrice] = None


class WBProduct(BaseModel):
    """Model product from raw search"""
    id: int
    name: str = "Без названия"
    supplier: str = "Неизвестный продавец"
    supplierId: int = 0
    reviewRating: float = 0.0
    feedbacks: int = 0
    totalQuantity: int = 0
    pics: int = 0
    sizes: list[WBSize] = Field(default_factory=list)

    description: str = ""
    characteristics: str = ""
    country: str = "Не указано"
    image_urls: str = ""

    def generate_images(self, basket_str: str):
        """Генерирует строку со ссылками на фото"""
        if not self.pics or not basket_str:
            return ""
        vol = self.id // 100000
        part = self.id// 1000
        base_url = f"https://basket-{basket_str}.wbbasket.ru/vol{vol}/part{part}/{self.id}/images/big"
        links = [f"{base_url}/{i}.webr" for i in range(1, self.pics+1)]
        self.image_urls = ", ".join(links)
    
    @property
    def sku(self) -> int:
        return self.id
    
    def get_price(self) -> float:
        for size in self.sizes:
            if size.wh>0 and size.price:
                return (size.price.product or size.price.basic)/100
        return 0.0
    
    def get_sizes_str(self) -> str:
        return ", ".join([s.name for s in self.sizes if s.name])
    
    def to_excel_dict(self):
        return {
            "link": f"https://www.wildberries.ru/catalog/{self.id}/detail.aspx",
            "sku": self.id,
            "name": self.name,
            "price": self.get_price(), 
            "description": self.description,
            "image_urls": self.image_urls,
            "characteristics": self.characteristics,
            "seller_name":self.supplier,
            "seller_link": f"https://www.wildberries.ru/seller/{self.supplierId}",
            "sizes": self.get_sizes_str(),
            "total_stocks": self.totalQuantity,
            "rating": self.reviewRating,
            "feedbacks": self.feedbacks,
            "country": self.country
        }





class AsyncWBParser: 
    URL = "https://www.wildberries.ru"
    SEARCH_URL =  "https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search"

    DEFAULT_PARAMS = {
        'ab_testing': 'false',
        'appType': '1', 
        'curr': 'rub',
        'dest': '-1257786',
        'hide_dtype': '9',
        'hide_vflags': '4294967296',
        'lang': 'ru',
        'page':'1',
        'query': 'dsaila pro',
        'resultset': 'catalog',
        'sort': 'popular',
        'spp': '30',
        'suppressSpellcheck': 'false',
    }

    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.cookies = {}
        self.user_agent = None

    @classmethod
    async def create(cls) -> "AsyncWBParser":
        self = cls()
        self.cookies, self.user_agent = await self._get_token_static()
        limits = httpx.Limits(
            max_keepalive_connections=30, max_connections=1000)
        self.client = httpx.AsyncClient(http2=True, limits=limits, headers={
                                        "User-Agent": self.user_agent}, cookies=self.cookies, timeout=10.0 )
        return self
    
    async def close(self):
        if self.client:
            await self.client.aclose()

    async def search_products_catalog(self, query: str, page: int, retry: int = 3)-> list[WBProduct]:
        params = self.DEFAULT_PARAMS.copy()
        params.update({"query": query, "page": str(page)})

        for attempt in range(1, retry+1):
            try: 
                resp = await self.client.get(self.SEARCH_URL, params=params)
                if resp.status_code == 498:
                    await self._refresh_token()
                    continue
                if resp.status_code != 200:
                    return [] 
                data = resp.json()
                products = data.get("products", [])
                return [WBProduct.model_validate(p) for p in products]
            except Exception as e:
                await asyncio.sleep(0.5)
        return [] 
    
    async def search_all_products(self, query: str, max_pages: Optional[int] = None) -> list[WBProduct]:
        page, all_products, = 1, []
        empty_pages_in_a_row, max_empty = 0,5
        with tqdm(desc=f"Сбор товаров по '{query}'", unit="page") as pbar:
            while True:
                products = await self.search_products_catalog(query, page)

                if len(products) == 0:
                    empty_pages_in_a_row+=1
                    if empty_pages_in_a_row>=max_empty:
                        break
                else:
                    empty_pages_in_a_row = 0
                    all_products.extend(products)
                page += 1
                pbar.update(1)
                if max_pages and max_pages == page:
                    break
                await asyncio.sleep(0.2)
        return all_products
                 


    
    @staticmethod
    async def _get_token_static() -> Tuple[dict, str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                channel="chrome",
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )

            # создаем контекст чтобы симулировать дея-сть пользователя (anti-bot)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 1024},
                java_script_enabled=True,
                )
            page = await context.new_page()
            await page.goto(AsyncWBParser.URL, wait_until="networkidle")

            await page.wait_for_event("framenavigated")

            cookies_list = await context.cookies()

            cookies = {c['name']: c['value'] for c in cookies_list}

            user_agent = await page.evaluate("()=> navigator.userAgent")

            await browser.close()
            print("cookies", cookies)
            print("user_agent", user_agent)
            return cookies, user_agent
        
    async def _refresh_token(self):
        self.cookies, self.user_agent = await self._get_token_static()
        if self.client: 
            self.client.headers.update({"User-Agent": self.user_agent})
            self.clilent.cookies = httpx.Cookies(self.cookies)



async def main() -> int:
    parser = await AsyncWBParser.create()
    try:
        products = await parser.search_all_products(
            "пальто из натуральной шерсти",
            5
        )
    except Exception as e: 
        await parser.close()
        return
    try:
        semaphore = asyncio.Semaphore(20)

        async def worker(product: WBProduct):
            async with semaphore:




   
    


if __name__ == "__main__":
    asyncio.run(main())