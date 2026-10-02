# BMORE — dealfinder

Find the lowest price on the **right** product from a seller you can trust, track it over
time, and find money you can claim back through price matching.

```
$ dealfinder compare --url "https://www.target.com/p/sony-wh-1000xm6/-/A-1" --prefer bestbuy

**Bottom line:** Buy new at amazon for $369.99 ($10.00 less than the next trusted seller);
that's at or below its 90-day low. Or open-box at bestbuy for $289.99, saving $80.00 — check the warranty.

|  | amazon ★ | bestbuy (open-box) | bestbuy | target | ebay |
|---|---|---|---|---|---|
| Price | $369.99 | $289.99 | $379.99 | $389.99 | $149.00 |
| Price history | at or below its 90-day low | — | — | — | — |
| Condition | new | open-box | new | new | new |
| Sold by | amazon | bestbuy | bestbuy | target | cheap_audio_99 |
| Flags | — | open-box grade: fair | — | — | third-party seller; suspiciously low: 39% of typical price |

**Excluded as a different product:**
- bestbuy: Sony WH-1000XM6 … Silver — different GTINs

**Price match:** Ask Best Buy for $10.00: show them the amazon listing at $369.99 …
```

There are two parts:

| Part | What it is |
|---|---|
| `dealfinder/` | A Python command-line app that compares prices, tracks them and finds price-match claims. |
| `.claude/skills/deal-finder/` | A Claude skill that does the same research conversationally using web search, and uses the app when it's installed. |

## Which sites, and why

The app uses official data feeds where they exist and reads public product pages only when you paste a link.
It never scrapes past bot protection and never uses affiliate links.

| Source | What you get | Cost | Setup |
|---|---|---|---|
| **Best Buy Products API** | Live sale price, regular price, UPC, model number, stock, **open-box offers** | Free (personal use) | Key from [developer.bestbuy.com](https://developer.bestbuy.com) → `BESTBUY_API_KEY` |
| **Keepa API** | Amazon's own price (sold by Amazon, not marketplace sellers) + **90-day average and low** | Paid subscription | [keepa.com](https://keepa.com/#!api) → `KEEPA_API_KEY` |
| **eBay Browse API** | Refurbished, used and marketplace prices — a check on what "too cheap" looks like | Free | App keys from [developer.ebay.com](https://developer.ebay.com) → `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` |
| **Any product page** (Target, Costco, B&H, Apple, Samsung, REI, Home Depot…) | Price, stock, condition, UPC and model number from the page's built-in product data (schema.org JSON-LD) | Free | Nothing — just pass `--url`. Checks `robots.txt` first; Amazon and Walmart usually block automated reads |

**Why not Amazon's or Walmart's own APIs?** Amazon's Product Advertising API and Walmart's
product API both require joining their affiliate programs. Keepa gives the
"sold by Amazon" price and its history without any affiliate tie.

**Why not scrape Google Shopping?** It breaks Google's terms and mixes in sponsored listings. Paid SERP
APIs exist if you want one, but Best Buy + Keepa + product pages cover the major US retailers.

## How prices are compared

1. **Confirm it's the same product.** Listings match only on the same UPC/GTIN or the same
   model number. Failing those, titles must be similar **and** must not conflict on storage, screen
   size, generation, year, pack count or tier ("Pro", "Max", "mini"…). Wrong-color and
   wrong-generation listings appear under *Excluded*, with the reason.
2. **Vet the seller.** Marketplace sellers (eBay, Amazon/Walmart third-party) are flagged and never
   chosen as the default pick. A price under 60% of the typical first-party price is flagged as
   *suspiciously low* (likely counterfeit, gray-market or a scam).
3. **Rank on total cost.** Price + known shipping, in-stock first. New and open-box/refurbished get
   separate recommendations, and open-box is only mentioned when it's actually cheaper.
4. **Judge the price against history.** Keepa (Amazon) and your own tracking history show
   whether today's price beats the 90-day average and low — or is a routine "sale."
5. **Show only what differs.** Table rows that are the same for every option are dropped.

## Price matching (what's automated, and what isn't)

`dealfinder` **finds** price-match and price-adjustment opportunities and tells you exactly what
to ask for, where, with which listing as proof, and by what date. It does **not** file claims,
log into accounts or contact retailers. A store employee checks every match by hand, and
automating claims would break retailer terms.

Current policies are in [`dealfinder/policies.json`](dealfinder/policies.json) (checked 2026-10-02 — they change, so the app always links the policy page):

| Retailer | Matches competitors? | Refunds the difference if *its own* price drops |
|---|---|---|
| Best Buy | Yes — Amazon, Walmart, Target, Costco, Sam's Club, B&H, Apple (sold by them, in stock); also after purchase within the return window | Within 15 days (longer for paid members) |
| Target | **No** — ended July 2025 | Within 14 days |
| Costco | No | Within 30 days |
| Walmart | No (since 2019) | No |
| Amazon | No | No — return and re-buy is the only route |

Three automatic checks:

- **Before you buy:** `--prefer bestbuy` tells you whether Best Buy will match a lower price elsewhere, so you can pick up today at the lower price.
- **After you buy:** `pricematch` / `track bought` watch for drops at the store you bought from (price adjustment) and at competitors it matches (competitor match), each with a deadline.
- **No-adjustment stores:** if Amazon's price drops, it suggests returning and re-buying while the return window is open.

## Setup

```bash
pip install -e .            # Python 3.10+; only dependency is requests
export BESTBUY_API_KEY=...  # optional, recommended
export KEEPA_API_KEY=...    # optional
export EBAY_CLIENT_ID=... EBAY_CLIENT_SECRET=...   # optional
dealfinder sources          # shows what's enabled
```

## Usage

```bash
# Compare
dealfinder compare "Sony WH-1000XM6"
dealfinder compare --upc 027242927896 --prefer bestbuy
dealfinder compare --url https://www.costco.com/... --url https://www.bhphotovideo.com/...
dealfinder compare --model MXP93LL/A --json          # for scripts / Claude

# Already bought it?
dealfinder pricematch --at bestbuy --price 449.99 --on 2026-09-25 --upc 027242927896

# Track prices
dealfinder track add "XM6 headphones" --upc 027242927896 --target 329
dealfinder track bought 1 --at bestbuy --price 449.99 --on 2026-09-25
dealfinder track list
dealfinder track check
```

### Scheduled alerts

`track check` refreshes every tracked item, saves prices to `~/.dealfinder/prices.db` (or `$DEALFINDER_DB`),
and sends an alert when a price:

- first reaches your target,
- drops 5% or more since the last check,
- or hits the lowest price you've seen.

It also tells you when a price-adjustment or competitor match is newly available on something you bought.

Alerts print to the terminal. They can also go to your phone or chat if you set `DEALFINDER_WEBHOOK_URL`:
an [ntfy.sh](https://ntfy.sh) topic URL, a Slack incoming webhook or a Discord webhook.

```cron
# twice a day — more often wastes API quota and looks like scraping
17 8,20 * * *  DEALFINDER_WEBHOOK_URL=https://ntfy.sh/your-topic /path/to/venv/bin/dealfinder track check --quiet
```

## Ground rules

- No affiliate or tracking links. Every URL is cleaned (`tag=`, `utm_*`, `irclickid`, Amazon `/ref=`…).
- No accounts, carts, orders or payment details, ever.
- Low volume and honest: requests identify themselves, `robots.txt` is respected, and a blocked page
  is reported as "check manually" — never retried around.
- Prices that couldn't be verified are labeled, never guessed.

## Development

```bash
pip install -e '.[dev]'
pytest
```

Tests run offline against saved API responses in `tests/fixtures/`.
