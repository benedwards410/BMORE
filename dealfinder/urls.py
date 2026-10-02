"""Strip affiliate and tracking parameters so every link we show is a clean product URL."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Exact parameter names (lower-cased) that only exist for tracking or affiliate credit.
_TRACKING_PARAMS = {
    "tag", "ref", "ref_", "ascsubtag", "linkcode", "linkid", "creative", "creativeasin",
    "camp", "affid", "aff_id", "affiliate", "affiliateid", "irgwc", "irclickid", "clickid",
    "gclid", "gbraid", "wbraid", "dclid", "fbclid", "msclkid", "yclid", "twclid", "ttclid",
    "cjevent", "cjdata", "ranmid", "raneaid", "ransiteid", "siteid", "wmlspartner",
    "sourceid", "veh", "afsrc", "mc_cid", "mc_eid", "_hsenc", "_hsmi", "srsltid",
    "pf_rd_p", "pf_rd_r", "pd_rd_r", "pd_rd_w", "pd_rd_wg", "content-id", "qid", "sr",
    "sprefix", "crid", "keywords", "acampid", "mkcid", "mkrid", "campid", "toolid",
    "customid", "mkevt", "_trkparms", "_trksid", "intcmp", "cmpid", "icid",
}
_TRACKING_PREFIXES = ("utm_", "pf_rd_", "pd_rd_", "aff_", "ir_", "cm_")

_AMAZON_ASIN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})", re.I)


def clean_url(url: str) -> str:
    """Return `url` without tracking/affiliate params. Amazon links collapse to /dp/<ASIN>."""
    if not url:
        return url
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()

    if "amazon." in host:
        m = _AMAZON_ASIN.search(parts.path)
        if m:
            return urlunsplit((parts.scheme or "https", parts.netloc, f"/dp/{m.group(1).upper()}", "", ""))
    if "ebay." in host and parts.path.startswith("/itm/"):
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))  # item id is in the path

    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    path = re.sub(r"/ref=[^/]*$", "", parts.path)  # Amazon-style trailing /ref=... segments
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(kept), ""))


def amazon_asin(url: str) -> str | None:
    m = _AMAZON_ASIN.search(urlsplit(url).path)
    return m.group(1).upper() if m else None


def retailer_from_url(url: str) -> str:
    """'https://www.bestbuy.com/site/...' -> 'bestbuy'. Falls back to the bare host."""
    host = urlsplit(url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    known = {
        "amazon.com": "amazon", "bestbuy.com": "bestbuy", "walmart.com": "walmart",
        "target.com": "target", "costco.com": "costco", "samsclub.com": "samsclub",
        "bhphotovideo.com": "bhphoto", "apple.com": "apple", "ebay.com": "ebay",
        "homedepot.com": "homedepot", "lowes.com": "lowes", "rei.com": "rei",
        "staples.com": "staples", "newegg.com": "newegg", "samsung.com": "samsung",
    }
    for domain, name in known.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host
