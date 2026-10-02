from datetime import date

from dealfinder.models import Condition, Offer
from dealfinder.tracker import Tracker


def o(price, condition=Condition.NEW, url="https://www.bestbuy.com/site/1.p?skuId=1"):
    return Offer(retailer="bestbuy", title="Thing", price=price, url=url, source="t",
                 in_stock=True, condition=condition)


def test_add_list_purchase_remove():
    t = Tracker(":memory:")
    i = t.add("Headphones", ["https://a"], gtin="027242927896", target_price=330)
    t.record_purchase(i, "bestbuy", 399.99, date(2026, 9, 28))
    [item] = t.items()
    assert item.urls == ["https://a"] and item.purchased_on == date(2026, 9, 28)
    t.remove(i)
    assert t.items() == []


def test_alerts_on_target_crossing_once_and_on_drops():
    t = Tracker(":memory:")
    item = t.get(t.add("Thing", ["u"], target_price=330))

    def check(price):
        alerts = t.evaluate(item, o(price))
        t.record(item.id, o(price))
        return [a.reason for a in alerts]

    assert check(400) == []
    assert check(399) == []                                   # 0.25% wiggle is noise
    assert any("dropped" in r for r in check(350))            # >5% drop
    reasons = check(329)
    assert any("target" in r for r in reasons) and any("lowest price seen" in r for r in reasons)
    assert not any("target" in r for r in check(328))         # already at target: no repeat


def test_open_box_history_is_kept_separate():
    t = Tracker(":memory:")
    item = t.get(t.add("Thing", ["u"]))
    t.record(item.id, o(400))
    assert t.evaluate(item, o(300, Condition.OPEN_BOX)) == []   # not a "drop" vs the new price
    assert t.stats(item.id, o(400)).current == 400
