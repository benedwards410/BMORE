"""Price sources. Each is optional; the app uses whichever ones have credentials."""

from .base import Source, SourceError
from .bestbuy import BestBuy
from .ebay import Ebay
from .jsonld import ProductPage
from .keepa import Keepa


def configured_sources() -> list:
    """API-backed sources that have credentials in the environment."""
    return [s for s in (BestBuy(), Keepa(), Ebay()) if s.available()]


__all__ = ["Source", "SourceError", "BestBuy", "Ebay", "Keepa", "ProductPage", "configured_sources"]
