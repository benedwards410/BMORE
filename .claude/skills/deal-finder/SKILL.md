---
name: deal-finder
description: Finds the best current price on a specific product across major US retailers, verifies it's the right model/generation, and returns a short bottom-line pick plus a differences-only comparison. Use whenever the user wants to buy something, asks "is this a good price," pastes a product listing or price, compares models or retailers, asks about sales, discounts, coupons, open-box or refurbished options, or says things like "where's it cheapest," "should I wait," or "which one should I get" — even if they never say the word "deal."
---

# Deal Finder

Help the user pay the least for the right product from a seller they can trust. This skill uses the built-in web search and web fetch tools, plus the local `dealfinder` CLI from this repo when it's installed. It registers with no outside service and earns nothing from what the user buys.

## Principles (why this skill exists)

- **No conflicts of interest.** Never add, generate, or prefer affiliate or tracking links. When sharing a link, give the clean product URL (strip tracking parameters such as `tag=`, `ref=`, `affid=`, `utm_`). If a source is a "deals" site that earns commission, say so in one line.
- **Right product first, price second.** A cheap price on the wrong generation is not a deal. Confirm the exact model before comparing prices.
- **Bottom line first.** Lead with the pick and the price. Details come after, and only the details that differ between options.
- **Privacy.** Don't save, log, or ask for shopping history, payment details, addresses, or account logins. Never place orders, add to carts, or sign up for anything on the user's behalf.

## Workflow

### 1. Pin down the exact product

- Pull the model number, SKU, or generation from what the user pasted (e.g., `MXP93LL/A`, "4th generation"). Model numbers beat product names; retailer titles are often wrong or vague.
- If the item has a newer version, check the release date and say so plainly. Flag when a "sale" is really clearance on a superseded model, and whether the old one is still a smart buy at that price.
- If the user named a category rather than a product ("noise-canceling earbuds under $150"), shortlist 2–4 candidates first, then price them.
- Only ask a clarifying question when the answer would change which product to price (e.g., size, storage tier, color with different pricing). Otherwise make a reasonable assumption and state it in one line.

### 2. Check prices across retailers

**If `dealfinder` is installed** (`dealfinder sources` succeeds), run it first. It reads real-time data from the Best Buy, Keepa and eBay APIs when they're configured, and it already matches products by UPC and model number, vets sellers and pulls price history:

```bash
dealfinder compare --upc <UPC> --json            # or --model <MODEL>, or --url <product page>, or "search terms"
dealfinder compare --url <URL> --prefer bestbuy  # can the user's preferred store price-match?
dealfinder pricematch --at <retailer> --price <paid> --on <YYYY-MM-DD> --upc <UPC>   # already bought it
```

Treat its output as the verified core of the answer. Use web search to fill gaps, such as retailers it couldn't reach or a store it reported as blocked. If a source is listed as not configured, don't ask the user for API keys mid-task; just search the web for that retailer.

Otherwise, search for the exact model at the retailers that matter for the category. Default US set:

- Manufacturer store (Apple, Samsung, etc.)
- Amazon (sold and shipped by Amazon, not third-party)
- Best Buy, Walmart, Target, Costco, Staples
- Category specialists when relevant (B&H, Home Depot, Lowe's, REI, etc.)

Also check, when they apply:

- **Open-box / certified refurbished** from the manufacturer or a major retailer (note warranty length).
- **Price history** (e.g., camelcamelcamel for Amazon) to judge whether today's price is genuinely low or a routine "sale."
- **Upcoming events** (Prime Day, Black Friday, back-to-school, new-model launches) if waiting is likely to save meaningful money.
- **Price-match policies** at the user's preferred retailer, if they have one. As of October 2026, Best Buy matches Amazon, Walmart, Target, Costco, Sam's Club, B&H and Apple. Target stopped matching competitors in July 2025, and Amazon, Walmart and Costco don't match competitors. Best Buy (15 days), Target (14 days) and Costco (30 days) refund the difference if their *own* price drops. The `dealfinder/policies.json` file in this repo holds the current terms, so check it, or the retailer's policy page, before quoting.

Use web_fetch on the product page when search snippets don't show a current price. If a price can't be verified, label it "unverified" rather than guessing.

### 3. Vet the seller

Flag any of these up front:

- Third-party marketplace sellers (Amazon, Walmart, eBay) instead of the retailer itself
- Prices far below every major retailer (likely counterfeit, gray-market, or scam)
- Unfamiliar sites with no clear return policy or contact info
- Listings missing the model number or showing a different one than the title

### 4. Report

Use this structure:

**Bottom line:** one or two sentences — which to buy, where, at what price, and why.

Then a compact table showing **only the rows where the options differ**. Drop any row where every option is the same (color, warranty, connectivity, etc.). Typical rows worth keeping when they differ:

| Row | Notes |
|---|---|
| Price (where) | Current price and retailer; note "was $X" only if verified |
| Generation / release | When a newer model exists |
| Key feature gaps | The 2–4 differences that actually change the decision |
| Battery / size / capacity | Use one consistent basis; say which (e.g., "with ANC on") |
| Availability | In stock, ship date, in-store pickup |
| Condition | New, open-box, refurbished + warranty |

After the table, at most 2–3 one-line "get this if…" picks. Note when retailer spec sheets conflict with the manufacturer's numbers and which you used.

Keep it to roughly one phone screen. Offer more detail only if asked.

### 5. Coupons and stacking (optional)

Mention only legitimate, verifiable savings: retailer coupons on the product page, store-card discounts, manufacturer promos, trade-in credit, education/military pricing. Don't recommend coupon-code browser extensions or unverified code sites. Credit-card or cashback portals can be mentioned as an option the user can choose, never as a requirement.

## Example

**Input:** "AirPods 4 with ANC are $120 at Best Buy — good deal vs. AirPods 5?"

**Output:**

**Bottom line:** Good deal if you charge on a pad; otherwise pay $9 more for AirPods 5 (USB-C) for noticeably better noise blocking.

| | AP4 ANC | AP5 USB-C | AP5 Wireless |
|---|---|---|---|
| Price | $120 (Best Buy) | $129 | $149 |
| Released | 2024 (superseded) | 2026 | 2026 |
| Noise blocking | Good | Up to 50% better | Up to 50% better |
| Wireless charging | Yes | No | Yes |
| Volume swipe | No | No | Yes |

- **Get AP4** if wireless charging matters and noise blocking is secondary.
- **Get AP5 Wireless** if you want the best open-fit pair with no tradeoffs.
