# MD Watch

A three-step pipeline that collects Maryland news and posts, drafts Drudge-style
entries for the MD Watch page, and publishes an entry only after a person has
read it and approved it.

```
feeds.json ──▶ fetch_feeds.js ──▶ pending_items.json ──▶ write_entries.js ──▶ draft_entries.json ──▶ publish_review.js ──▶ published_log.json
               (can be scheduled)                          (can be scheduled)                          (a person, at a terminal)
```

| Step | Script | Reads | Writes |
| --- | --- | --- | --- |
| 1 | `fetch_feeds.js` | `feeds.json`, `draft_entries.json` (read only) | `pending_items.json`, `seen_items.db` |
| 2 | `write_entries.js` | `pending_items.json` | `draft_entries.json` |
| 3 | `publish_review.js` | `draft_entries.json` | `published_log.json` (append only), review marks in `draft_entries.json` |

`publish_review.js` is the only script that ever writes `published_log.json`.

## Setup

Requires Node.js 22 or newer.

```sh
npm install
cp .env.example .env   # then fill in the keys
```

`.env` (loaded automatically by steps 1 and 2; never committed):

| Variable | Needed by | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | `write_entries.js` | Writes the drafts with Claude |
| `X_BEARER_TOKEN` | `fetch_feeds.js` | Reads X accounts listed in `feeds.json` (a bearer token from an X developer app; RSS feeds need no key) |

## Running it

```sh
node fetch_feeds.js        # 1. collect new items
node write_entries.js      # 2. draft entries (add --no-link-check to skip the link check)
node publish_review.js     # 3. review and approve, one section at a time
```

Steps 1 and 2 are safe to run on a schedule (cron, launchd, Task Scheduler): each
run takes a lock so overlapping runs cannot corrupt the files, and they never
publish anything. Step 3 refuses to run without a person at an interactive
terminal, takes no options, and never treats a blank or unexpected answer as
approval.

### How a batch moves through

1. Every run of `fetch_feeds.js` adds new items to the current batch in
   `pending_items.json`. Items it has already seen (by GUID or link, recorded in
   `seen_items.db`) are counted as duplicates and dropped; items that match no
   category are discarded.
2. `write_entries.js` drafts one entry per category that has items, and records
   which items the drafts covered. It will not overwrite drafts that are partly
   reviewed.
3. `publish_review.js` shows each draft and asks for one of three decisions:
   - **approve** — appended to `published_log.json` as drafted;
   - **edit** — change the opening text, a headline, a quote, a context line, or
     remove a highlight, then approve; the published record carries the edits and
     a before/after list. Links cannot be edited: they always come from the
     original post;
   - **skip** — nothing is published for that section this round.
   Stopping early (`q` or Ctrl+C) keeps the decisions already made; the next
   session offers only what is left.
4. Once every draft in the batch has a decision, the next `fetch_feeds.js` run
   starts a new batch, carrying over any items that arrived after the drafts were
   written.

## feeds.json

```jsonc
{
  "settings": { "request_timeout_ms": 15000, "concurrency": 4, "x_max_posts": 20 },
  "feeds": [
    { "name": "Maryland Matters", "url": "https://marylandmatters.org/feed/", "type": "news_org" },
    { "name": "Wes Moore", "url": "https://x.com/iamwesmoore", "type": "campaign_official" },
    { "name": "WeRateDogs", "url": "https://x.com/dog_rates", "type": "relief" },
    { "name": "Someone", "url": "https://example.org/feed", "type": "reporter", "handle": "@someone", "enabled": false }
  ],
  "categories": { "politicians": ["governor", "..."], "crime": ["..."], "education": ["..."], "cost_of_living": ["..."] }
}
```

- `url` is an RSS/Atom feed, or an X profile URL (`https://x.com/handle`), which
  is read through the X API.
- `type` is one of `news_org`, `reporter`, `independent`, `citizen_commentary`,
  `campaign_official`, `relief`. It decides how an item is presented:
  - `news_org`, `reporter` — a bold Drudge-style headline, then a plain line
    naming who reported it, then the link.
  - `independent`, `citizen_commentary`, `campaign_official` — the headline is a
    quote copied from the post, `"[quote]" —@handle`, over the fixed line
    `Commentary. Please, fact check yourself.`, then the link.
  - `relief` — funny, lighthearted accounts. These skip keyword matching entirely
    and go straight into the `relief` section; neutral clips get a headline and a
    line naming the account, a creator's own framing of events gets the quote
    format above.
- `handle` (optional) is the @handle used to attribute quotes; for X sources and
  Reddit posts it is worked out automatically.
- `enabled: false` keeps a source in the list without fetching it.
- `categories` maps each civic section to its keywords. Matching is
  case-insensitive on whole words, includes simple plurals, allows a trailing `*`
  (`arrest*`), and phrases may be hyphenated in the text. A keyword in the title
  counts three times a keyword in the body; the highest-scoring category wins.
  `relief` is not a keyword category and must not be listed here.

## Files the pipeline writes

All of them are ignored by git. Set `MD_WATCH_DIR` to keep them somewhere other
than the script directory.

- `seen_items.db` — SQLite: every item ever processed, plus the newest post id
  fetched per X account. Delete it to start over (everything will be re-fetched
  as new).
- `pending_items.json` — the current batch, grouped by category, with the source
  name, type and handle on every item.
- `draft_entries.json` — one draft entry per category: `inference_paragraph`
  (or `setup_line` for relief), 2–3 `highlights` (each with `headline`,
  `context_line`, `link`), the full list of `sources`, anything `left_out` and
  why, `review_flags` a person should look at, a `markdown` rendering, and the
  `review` decision once made.
- `published_log.json` — the list of approved entries, in order. It only ever
  grows.

## Tests

```sh
npm test
```

The tests run against a local fixture server (good, broken, slow and missing
feeds, a fake X API) and a stand-in for Claude, so they need no network access
or API keys.
