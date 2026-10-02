from datetime import date

from dealfinder.compare import compare
from dealfinder.finder import Finder
from dealfinder.models import Condition, Offer, PriceStats
from dealfinder.pricematch import Purchase, after_purchase, before_purchase, load_policies
from dealfinder.report import render
from dealfinder.sources import BestBuy, Ebay, Keepa, ProductPage

from .conftest import FakeHttp, FakeResponse

GTIN = "00027242927896"


def o(retailer, price, **kw):
    kw.setdefault("gtin", GTIN)
    return Offer(retailer=retailer, title=kw.pop("title", "Sony WH-1000XM6 Black"), price=price,
                 url=kw.pop("url", f"https://{retailer}.example/p"), source="test", **kw)


# --- compare ----------------------------------------------------------------

def test_compare_picks_cheapest_trusted_new_and_flags_scams():
    offers = [
        o("bestbuy", 379.99, in_stock=True),
        o("target", 389.99, in_stock=True),
        o("amazon", 369.99, in_stock=True),
        o("ebay", 149.00, sold_by_retailer=False, seller="cheap_audio_99"),
        o("walmart", 359.99, in_stock=False),
        o("bestbuy", 319.99, condition=Condition.OPEN_BOX, in_stock=True),
        o("bestbuy", 279.99, gtin="00027242927902", title="Sony WH-1000XM6 Silver"),
    ]
    c = compare(offers, reference=offers[0])
    assert c.best_new.offer.retailer == "amazon"
    assert c.best_alternative.offer.price == 319.99
    scam = next(r for r in c.ranked if r.offer.retailer == "ebay")
    assert not scam.trusted and any("suspiciously low" in f for f in scam.flags)
    assert any("out of stock" in f for r in c.ranked if r.offer.retailer == "walmart" for f in r.flags)
    assert [x.title for x, _ in c.rejected] == ["Sony WH-1000XM6 Silver"]


def test_open_box_not_cheaper_than_new_is_not_suggested():
    offers = [o("bestbuy", 300.0), o("target", 310.0, condition=Condition.REFURBISHED)]
    assert compare(offers).best_alternative is None


def test_report_shows_bottom_line_and_drops_identical_rows():
    offers = [o("bestbuy", 379.99, in_stock=True, shipping=0.0),
              o("amazon", 369.99, in_stock=True, shipping=0.0)]
    text = render(compare(offers, history={"https://amazon.example/p": PriceStats(avg_90d=419.99, low_90d=369.99)}))
    assert "**Bottom line:** Buy new at amazon for $369.99 ($10.00 less than the next trusted seller)" in text
    assert "at or below its 90-day low" in text
    assert "| Price |" in text
    assert "| Condition |" not in text and "| Shipping |" not in text   # same for both → dropped


def test_report_when_nothing_trusted():
    text = render(compare([o("ebay", 100.0, sold_by_retailer=False)]))
    assert "No trusted, in-stock offer" in text


# --- price matching ---------------------------------------------------------

POLICIES = load_policies()


def test_policies_load_and_reflect_target_change():
    assert "amazon" in POLICIES["bestbuy"].matches_competitors
    assert POLICIES["target"].matches_competitors == []


def test_before_purchase_best_buy_can_match_amazon():
    op = before_purchase("bestbuy", [o("bestbuy", 379.99, in_stock=True), o("amazon", 369.99, in_stock=True),
                                     o("ebay", 300.0, sold_by_retailer=False)], POLICIES)
    assert op.kind == "match-before-buying" and op.amount == 10.0 and op.evidence.retailer == "amazon"


def test_before_purchase_target_no_longer_matches():
    assert before_purchase("target", [o("target", 389.99), o("amazon", 369.99)], POLICIES) is None


def test_after_purchase_price_adjustment_within_window():
    p = Purchase("bestbuy", 449.99, date(2026, 9, 25))
    ops = after_purchase(p, [o("bestbuy", 379.99, in_stock=True), o("amazon", 369.99, in_stock=True)],
                         POLICIES, today=date(2026, 10, 2))
    kinds = {op.kind: op for op in ops}
    assert kinds["price-adjustment"].amount == 70.0
    assert kinds["price-adjustment"].deadline == date(2026, 10, 10)
    assert kinds["competitor-match"].amount == 80.0
    assert ops[0].kind == "competitor-match"     # biggest first


def test_after_purchase_outside_window_finds_nothing():
    p = Purchase("bestbuy", 449.99, date(2026, 8, 1))
    assert after_purchase(p, [o("bestbuy", 379.99)], POLICIES, today=date(2026, 10, 2)) == []


def test_after_purchase_ignores_marketplace_and_open_box_evidence():
    p = Purchase("bestbuy", 449.99, date(2026, 9, 30))
    ops = after_purchase(p, [o("amazon", 300.0, sold_by_retailer=False),
                             o("bestbuy", 319.99, condition=Condition.OPEN_BOX)], POLICIES, today=date(2026, 10, 2))
    assert ops == []


def test_after_purchase_amazon_suggests_return_and_rebuy():
    p = Purchase("amazon", 399.99, date(2026, 9, 30))
    [op] = after_purchase(p, [o("amazon", 369.99)], POLICIES, today=date(2026, 10, 2))
    assert op.kind == "return-and-rebuy" and op.amount == 30.0


# --- finder end-to-end with fake APIs ---------------------------------------

def test_finder_gathers_from_every_source(fixture):
    http = FakeHttp({
        "openBox": FakeResponse(body=fixture("bestbuy_openbox.json")),
        "api.bestbuy.com/v1/products": FakeResponse(body=fixture("bestbuy_products.json")),
        "api.keepa.com": FakeResponse(body=fixture("keepa_product.json")),
        "oauth2/token": FakeResponse(body={"access_token": "t", "expires_in": 7200}),
        "item_summary/search": FakeResponse(body=fixture("ebay_search.json")),
        "robots.txt": FakeResponse(404, text=""),
        "target.com/p": FakeResponse(text=fixture("target_page.html")),
    })
    f = Finder(BestBuy("k", http=http), Keepa("k", http=http), Ebay("i", "s", http=http), ProductPage(http=http))
    g = f.gather(urls=["https://www.target.com/p/sony/-/A-1"])
    assert g.gtin == GTIN and g.reference.retailer == "target"
    assert {x.retailer for x in g.offers} == {"target", "bestbuy", "amazon", "ebay"}
    assert any(x.condition is Condition.OPEN_BOX and x.gtin == GTIN for x in g.offers)
    assert "https://www.amazon.com/dp/B0DXM6SONY" in g.history

    c = compare(g.offers, reference=g.reference, history=g.history)
    assert c.best_new.offer.retailer == "amazon" and c.best_new.offer.price == 369.99
    assert c.best_alternative.offer.price == 289.99          # open-box "fair" grade
    assert any("Silver" in x.title for x, _ in c.rejected)   # wrong color SKU excluded
    text = render(c)
    assert "Buy new at amazon for $369.99" in text and "90-day low" in text


def test_finder_reports_missing_sources(monkeypatch):
    for k in ("BESTBUY_API_KEY", "KEEPA_API_KEY", "EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    g = Finder(page=ProductPage(http=FakeHttp({}))).gather(query="anything")
    assert g.offers == [] and any("API keys" in w for w in g.warnings)


def test_free_text_search_anchors_on_best_title_match_not_cheapest(fixture):
    products = fixture("bestbuy_products.json")
    products["products"].insert(0, {
        "sku": 1111111, "name": "Insignia - Replacement Ear Pads for Sony Headphones", "salePrice": 12.99,
        "regularPrice": 12.99, "upc": "600603180017", "modelNumber": "NS-PADS", "onlineAvailability": True,
        "condition": "New", "freeShipping": True})
    http = FakeHttp({
        "openBox": FakeResponse(body={"results": []}),
        "api.bestbuy.com/v1/products": FakeResponse(body=products),
        "api.keepa.com": FakeResponse(body=fixture("keepa_product.json")),
    })
    f = Finder(BestBuy("k", http=http), Keepa("k", http=http), Ebay(None, None, http=http),
               ProductPage(http=http), include_ebay=False)
    g = f.gather(query="Sony WH-1000XM6 Black headphones")
    assert g.reference.model_number == "WH1000XM6/B" and g.gtin == GTIN
    keepa_call = [c for c in http.calls if "keepa" in c[1]][0]
    assert keepa_call[2]["params"]["code"] == "027242927896"
    c = compare(g.offers, reference=g.reference, history=g.history)
    assert c.best_new.offer.retailer == "amazon"
    assert any("Ear Pads" in x.title for x, _ in c.rejected)
