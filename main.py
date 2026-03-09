from playwright.async_api import async_playwright

import pandas as pd
from datetime import datetime
from selenium.webdriver.common.by import By

from selenium.webdriver import Keys
from config import WBConfig
import asyncio
import argparse
import time
import os
import re


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("query",type=str, help="Search query (Russian)")
    return p.parse_args()


async def parse(page, data):
    await page.wait_for_selector("div.product-card__wrapper")
    product_info = page.locator("div.product-card__wrapper")
    count = await product_info.count()
    print(count)
    for i in range(count):
        try:
            wrapper = product_info.nth(i)
            product_name_locator = wrapper.locator(
                "span.product-card__name"
            ).nth(0)
            product_link_locator = wrapper.locator("a.product-card__link")
            product_price_locator = wrapper.locator(
                "ins.price__lower-price"
            ).nth(0)
            product_rating_locator = wrapper.locator("span.address-rate-mini")
            product_date_locator = wrapper.locator(
                "a.product-card__add-basket > span.btn-text"
            )

            (
                product_rating,
                product_date,
                product_price_row,
                product_link,
                product_name,
            ) = await asyncio.gather(
                product_rating_locator.inner_text(),
                product_date_locator.inner_text(),
                product_price_locator.text_content(),
                product_link_locator.get_attribute("href"),
                product_name_locator.inner_text(),
            )

            product_price = re.sub(
                r"[\u202f\xa0]", "", product_price_row
            ).strip()

            if "/" in product_name:
                product_name = product_name.replace("/", "", 1).strip()

            if "" == product_rating:
                product_rating = "Нет оценок"
            
            data.append(
                    {
                        "Название карточки": product_name,
                        "Ссылка": product_link,
                        "Цена": product_price,
                        "Рейтинг": product_rating,
                        "Дата доставки": product_date,
                    }
                )
        except Exception as e:
            print(f"Ошибка при обработке {i} карточки: {e}")

async def main() -> int:
    args = parse_args()
    print(args.query)
    if args.query:
        os.environ["WB_QUERY"] = args.query
    
    cfg = WBConfig()
    data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        # создаем контекст чтобы симулировать дея-сть пользователя (anti-bot)
        context = await browser.new_context(
            user_agent=cfg.user_agent,
            viewport={"width": 1280, "height": 1024},
            java_script_enabled=True,
        )

        page = await context.new_page()
        
        await page.goto(
            "https://www.wildberries.ru/catalog/0/search.aspx?search=Пальто"
        )
        prev_len = 0

        while True:
            #await auto_scroll(page)
            await parse(page, data)
            if len(data) == prev_len:
                print("Новые карточки не появились — стоп")
                break
            prev_len = len(data)
            await asyncio.sleep(1)
            if not await goto_next(page):
                break
        await browser.close()
    
async def auto_scroll(page, scroll_times=5, pause=0.2):
    await page.wait_for_selector("div.product-card__wrapper")
    for _ in range(scroll_times):
        await page.mouse.wheel(0, 1700)
        await asyncio.sleep(pause)
    
async def goto_next(browser_page):
        # Все переходные кнопки (a)
        buttons = browser_page.locator("a.pagination__item.pagination-item")
        if await buttons.count() == 0:
            print("Кнопки пагинации не найдены")
            return False
        # Активная страница (span)
        active = browser_page.locator("span.pagination__item.active")
        if await active.count() == 0:
            print("Активная страница (span.active) не найдена")
            return False
        
        active_text = await active.text_content()
        print(f"Активная страница: {active_text}")

        # Переход на следующую
        next_btn = None
        for i in range(await buttons.count()):
            text = await buttons.nth(i).text_content()
            if text == str(int(active_text) + 1):  # ищем следующую
                next_btn = buttons.nth(i)
                break

        if next_btn:
            print(f"Переход на страницу: {int(active_text) + 1}")
            await next_btn.click()
            await browser_page.wait_for_selector("div.product-card__wrapper")
            await asyncio.sleep(0.5)
            return True
        else:
            print("Последняя страница достигнута")
            return False

if __name__ == "__main__":
    asyncio.run(main())