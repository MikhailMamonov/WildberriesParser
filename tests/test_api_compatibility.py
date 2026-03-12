import pytest 
from ..main import WBProduct, AsyncWBParser


@pytest.mark.asyncio
async def test_current_wb_api_structure():
    parser = AsyncWBParser()
    products = await parser.search_products_catalog("пальто", page=1)

    assert len(products)>0, "API вернуло 0 товаров.Возможно, изменились параметры запроса или URL"

    assert isinstance(products[0], WBProduct)