import os


class WBConfig:
    query: str = os.getenv("WB_QUERY", "пальто из натуральной шерсти")
    lang: str = os.getenv("WB_LANG", "ru")
    output_lang: str = os.getenv("WB_OUTPUT_LANG", "ru")
    base_url: str = os.getenv("WB_BASE_URL", "http://www.wildberries.ru/")
    search_base_url: str = os.getenv(
        "WB_SEARCH_BASE_URL",
        "https://u-search.wb.ru/exactmatch/ru/common/v18/search",
    )
    card_base_url: str = os.getenv(
        "WB_CARD_BASE_URL",
        "https://card.wb.ru/cards/v4/detail",
    )
    max_pages: int = 10
    user_agent: str = os.getenv(
        "WB_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )