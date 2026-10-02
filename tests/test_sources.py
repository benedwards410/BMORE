import pytest

from dealfinder.models import Condition
from dealfinder.sources import BestBuy, Ebay, Keepa, ProductPage, SourceError
from dealfinder.sources.jsonld import parse_product_page
from dealfinder.sources.keepa import stats_from_product

from .conftest import FakeHttp, FakeResponse


def test_bestbuy_parses_products_and_builds_clean_urls(fixture):
    http = FakeHttp({"api.bestbuy.com/v1/products": FakeResponse(body=fixture("bestbuy_products.json"))})
    offers = BestBuy(api_key="k", http=http).lookup(gtin="027242927896")
    black = offers[0]
    assert black.price == 379.99 and black.regular_price == 449.99 and black.shipping == 0.0
    assert black.gtin == "00027242927896" and black.model_number == "WH1000XM6/B"
    assert black.url == "https://www.bestbuy.com/site/6505727.p?skuId=6505727"
    assert offers[1].in_stock is False
    method, url, kw = http.calls[0]
    assert "upc=027242927896" in url and kw["params"]["apiKey"] == "k"


def test_bestbuy_search_builds_search_terms(fixture):
    http = FakeHttp({"api.bestbuy.com": FakeResponse(body={"products": []})})
    BestBuy(api_key="k", http=http).search("Sony WH-1000XM6 headphones")
    assert "search=Sony&search=WH&search=1000XM6&search=headphones" in http.calls[0][1]


def test_bestbuy_open_box(fixture):
    http = FakeHttp({"openBox": FakeResponse(body=fixture("bestbuy_openbox.json"))})
    offers = BestBuy(api_key="k", http=http).open_box(6505727)
    assert [o.price for o in offers] == [319.99, 289.99]
    assert all(o.condition is Condition.OPEN_BOX for o in offers)
    assert "open-box grade: excellent" in offers[0].notes


def test_bestbuy_without_key_raises(monkeypatch):
    monkeypatch.delenv("BESTBUY_API_KEY", raising=False)
    bb = BestBuy(http=FakeHttp({}))
    assert not bb.available()
    with pytest.raises(SourceError):
        bb.search("headphones")


def test_ebay_marks_everything_third_party_and_cleans_urls(fixture):
    http = FakeHttp({
        "oauth2/token": FakeResponse(body={"access_token": "tok", "expires_in": 7200}),
        "item_summary/search": FakeResponse(body=fixture("ebay_search.json")),
    })
    offers = Ebay("id", "secret", http=http).lookup(gtin="027242927896")
    assert all(not o.sold_by_retailer for o in offers)
    assert offers[0].url == "https://www.ebay.com/itm/1234"
    assert offers[0].shipping == 0.0 and offers[1].shipping is None
    assert offers[1].condition is Condition.REFURBISHED
    search_call = [c for c in http.calls if "item_summary" in c[1]][0]
    assert search_call[2]["params"]["gtin"] == "027242927896"
    assert search_call[2]["headers"]["Authorization"] == "Bearer tok"


def test_keepa_stats_and_offer(fixture):
    data = fixture("keepa_product.json")
    stats = stats_from_product(data["products"][0])
    assert (stats.current, stats.avg_90d, stats.low_90d, stats.all_time_low) == (369.99, 419.99, 369.99, 349.99)
    assert stats.verdict(369.99) == "at or below its 90-day low"

    k = Keepa(api_key="k", http=FakeHttp({"api.keepa.com": FakeResponse(body=data)}))
    [o] = k.lookup(gtin="027242927896")
    assert o.retailer == "amazon" and o.sold_by_retailer and o.price == 369.99
    assert o.url == "https://www.amazon.com/dp/B0DXM6SONY"
    assert k.history(o) is k.stats_by_url[o.url]


def test_keepa_falls_back_to_marketplace_when_amazon_has_no_offer(fixture):
    data = fixture("keepa_product.json")
    data["products"][0]["stats"]["current"][0] = -1
    k = Keepa(api_key="k", http=FakeHttp({"api.keepa.com": FakeResponse(body=data)}))
    [o] = k.lookup(asin="B0DXM6SONY")
    assert not o.sold_by_retailer and o.price == 355.00


def test_jsonld_product_page(fixture):
    [o] = parse_product_page(fixture("target_page.html"), "https://www.target.com/p/sony/-/A-1?utm_source=x")
    assert o.retailer == "target" and o.price == 389.99 and o.in_stock is True
    assert o.gtin == "00027242927896" and o.model_number == "WH1000XM6/B" and o.brand == "Sony"
    assert o.sold_by_retailer and o.url == "https://www.target.com/p/sony/-/A-1"


def test_jsonld_marketplace_seller_detected():
    html = """<script type="application/ld+json">{"@type":"Product","name":"Thing",
      "offers":{"price":"10","seller":{"name":"RandomShop LLC"}}}</script>"""
    [o] = parse_product_page(html, "https://www.walmart.com/ip/1")
    assert not o.sold_by_retailer and o.seller == "RandomShop LLC"


def test_meta_tag_fallback(fixture):
    [o] = parse_product_page(fixture("meta_only_page.html"), "https://acme.example/blender")
    assert o.price == 89.0 and o.source == "meta-tags"


def test_product_page_respects_robots_and_blocks(fixture):
    robots_deny = FakeHttp({"robots.txt": FakeResponse(text="User-agent: *\nDisallow: /")})
    with pytest.raises(SourceError, match="robots.txt"):
        ProductPage(http=robots_deny).fetch("https://shop.example/p/1")

    blocked = FakeHttp({"robots.txt": FakeResponse(404, text=""), "/p/1": FakeResponse(403, text="no bots")})
    with pytest.raises(SourceError, match="blocked"):
        ProductPage(http=blocked).fetch("https://shop.example/p/1")

    ok = FakeHttp({"robots.txt": FakeResponse(404, text=""), "/p/1": FakeResponse(text=fixture("target_page.html"))})
    assert ProductPage(http=ok).fetch("https://shop.example/p/1")[0].price == 389.99


def test_bestbuy_search_keeps_single_digit_generation(fixture):
    http = FakeHttp({"api.bestbuy.com": FakeResponse(body={"products": []})})
    BestBuy(api_key="k", http=http).search("AirPods 4")
    assert "search=AirPods&search=4" in http.calls[0][1]
