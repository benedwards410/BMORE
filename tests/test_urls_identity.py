from dealfinder.identity import (
    conflicting_attributes, match, normalize_gtin, normalize_model, title_similarity, variant_attributes,
)
from dealfinder.models import Condition, Offer
from dealfinder.urls import amazon_asin, clean_url, retailer_from_url


def offer(title, **kw):
    return Offer(retailer=kw.pop("retailer", "x"), title=title, price=kw.pop("price", 100.0),
                 url=kw.pop("url", "https://x.com"), source="test", **kw)


# --- URLs -------------------------------------------------------------------

def test_clean_url_strips_affiliate_and_tracking_params():
    url = "https://www.bestbuy.com/site/6505727.p?skuId=6505727&utm_source=x&irclickid=abc&ref=deals&gclid=1"
    assert clean_url(url) == "https://www.bestbuy.com/site/6505727.p?skuId=6505727"


def test_clean_url_collapses_amazon_links_to_dp_asin():
    url = "https://www.amazon.com/Sony-Headphones/dp/b0dxm6sony/ref=sr_1_3?tag=dealsite-20&keywords=sony"
    assert clean_url(url) == "https://www.amazon.com/dp/B0DXM6SONY"
    assert amazon_asin(url) == "B0DXM6SONY"


def test_clean_url_keeps_meaningful_params():
    assert clean_url("https://www.target.com/p/-/A-12345?preselect=678") == "https://www.target.com/p/-/A-12345?preselect=678"


def test_retailer_from_url():
    assert retailer_from_url("https://www.bestbuy.com/site/x") == "bestbuy"
    assert retailer_from_url("https://smile.amazon.com/dp/X") == "amazon"
    assert retailer_from_url("https://shop.example.org/p") == "shop.example.org"


# --- GTIN / model -----------------------------------------------------------

def test_normalize_gtin_pads_and_validates():
    assert normalize_gtin("0 27242 92789 6") == "00027242927896"
    assert normalize_gtin("027242927895") is None   # bad check digit
    assert normalize_gtin("12345") is None


def test_normalize_model_ignores_punctuation_and_case():
    assert normalize_model("MXP93LL/A") == normalize_model("mxp93ll-a")


# --- variant attributes -----------------------------------------------------

def test_variant_attributes_extracts_storage_generation_screen():
    a = variant_attributes('Apple iPad Air 11" M3 (2025) 256GB Wi-Fi')
    assert a["storage"] == "256gb" and a["screen"] == "11" and a["year"] == "2025" and a["tier"] == "air"
    assert variant_attributes("AirPods (4th generation)")["generation"] == "4"
    assert variant_attributes("Echo Dot Gen 5")["generation"] == "5"


def test_conflicts_catch_wrong_storage_and_tier():
    assert "storage" in conflicting_attributes("iPhone 17 128GB Black", "iPhone 17 256GB Black")
    assert "tier" in conflicting_attributes("AirPods Pro 3", "AirPods 4")
    assert conflicting_attributes("Sony WH-1000XM6 Black", "Sony WH1000XM6 Headphones (Black)") == []


def test_title_similarity_tolerates_retailer_noise():
    assert title_similarity("Sony WH-1000XM6 Wireless Headphones Black",
                            "Sony - WH-1000XM6 Wireless Noise Canceling Over-the-Ear Headphones - Black") >= 0.75


# --- match ------------------------------------------------------------------

def test_match_prefers_gtin_over_title():
    a = offer("Totally different title", gtin="00027242927896")
    b = offer("Sony headphones", gtin="027242927896")
    assert match(a, b).same and match(a, b).confidence == "gtin"


def test_match_rejects_different_gtin_even_with_same_title():
    a = offer("Sony WH-1000XM6 Black", gtin="027242927896")
    b = offer("Sony WH-1000XM6 Black", gtin="027242927902")
    assert not match(a, b).same


def test_match_by_model_number():
    assert match(offer("A", model_number="WH1000XM6/B"), offer("B", model_number="wh1000xm6-b")).same


def test_match_title_rejects_different_generation():
    m = match(offer("Apple AirPods (3rd generation)"), offer("Apple AirPods (4th generation)"))
    assert not m.same and "generation" in m.reason


def test_condition_parse():
    assert Condition.parse("Certified - Refurbished") is Condition.REFURBISHED
    assert Condition.parse("Open-Box Excellent") is Condition.OPEN_BOX
    assert Condition.parse("Pre-Owned") is Condition.USED
    assert Condition.parse("New") is Condition.NEW
