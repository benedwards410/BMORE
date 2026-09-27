#!/usr/bin/env node
'use strict';

/**
 * MD Watch, step 1 of 3: fetch_feeds.js
 *
 * Reads feeds.json, fetches every enabled source, and queues the items that are
 * new since the last run in pending_items.json, grouped by category.
 *
 *  - A source is either an RSS/Atom feed (parsed with rss-parser) or an X account
 *    given as https://x.com/<handle>, read through the X API (needs X_BEARER_TOKEN).
 *  - Items from civic sources are filed by keyword matching into the categories
 *    defined in feeds.json; an item that matches none of them is discarded.
 *  - Sources of type "relief" skip keyword matching: every new item goes to "relief".
 *  - Every item this script has processed is remembered in seen_items.db (SQLite),
 *    so nothing is queued twice.
 *  - A source that fails (timeout, HTTP error, malformed XML, ...) is logged and
 *    skipped; the run carries on with the rest.
 *
 * pending_items.json holds one batch: everything queued since the previous batch
 * was drafted and reviewed. When draft_entries.json shows the current batch fully
 * reviewed, the next run starts a new batch, carrying over any items the drafts
 * did not cover. draft_entries.json is only read here, never written, and
 * published_log.json is never touched.
 */

const crypto = require('node:crypto');
const path = require('node:path');
const Parser = require('rss-parser');
const Database = require('better-sqlite3');
const { PATHS, RELIEF, readJsonFile, writeJsonAtomic, isHttpUrl, mapLimit, loadEnvFile, withLock } = require('./lib/common');

const SOURCE_TYPES = ['news_org', 'reporter', 'independent', 'citizen_commentary', 'campaign_official', RELIEF];

const DEFAULT_SETTINGS = {
  request_timeout_ms: 15000,
  concurrency: 4,
  user_agent: 'MD-Watch/1.0 (local news aggregator)',
  x_max_posts: 20,
};

const MAX_RESPONSE_BYTES = 10 * 1024 * 1024;
const FEED_ACCEPT = 'application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5';
const TITLE_WEIGHT = 3; // a keyword in the headline counts three times as much as one in the body
const WORD_CHAR = '[\\p{L}\\p{N}]';
const PHRASE_GAP = '[\\s\\u2010\\u2011-]+'; // words of a keyword phrase may be split by spaces or hyphens
const X_HOSTS = new Set(['x.com', 'www.x.com', 'mobile.x.com', 'twitter.com', 'www.twitter.com', 'mobile.twitter.com']);
const X_LINK_HOSTS = new Set([...X_HOSTS, 't.co', 'pic.x.com', 'pic.twitter.com']);

// Plain-text versions of fields rss-parser does not convert on its own.
const RSS_ITEM_FIELDS = [
  ['title', 'titleText', { includeSnippet: true }],
  ['summary', 'summaryText', { includeSnippet: true }],
  ['media:group', 'mediaGroup'], // YouTube keeps a video's description here
];

/** A problem with one source: logged, and the run moves on. */
class SourceError extends Error {}

// ---------------------------------------------------------------------------
// Configuration

function loadConfig(file) {
  const raw = readJsonFile(file);
  if (!raw) throw new Error(`${path.basename(file)} not found (looked in ${path.dirname(file)})`);
  const problems = [];

  const settings = { ...DEFAULT_SETTINGS, ...raw.settings };
  for (const key of ['request_timeout_ms', 'concurrency', 'x_max_posts']) {
    if (!Number.isInteger(settings[key]) || settings[key] < 1) problems.push(`settings.${key} must be a positive whole number`);
  }
  if (settings.x_max_posts < 5 || settings.x_max_posts > 100) problems.push('settings.x_max_posts must be between 5 and 100');
  if (typeof settings.user_agent !== 'string' || !settings.user_agent.trim()) problems.push('settings.user_agent must be a non-empty string');

  const categories = raw.categories;
  if (!categories || typeof categories !== 'object' || Array.isArray(categories) || !Object.keys(categories).length) {
    problems.push('"categories" must map each category name to a list of keywords');
  } else {
    for (const [name, keywords] of Object.entries(categories)) {
      if (name === RELIEF) {
        problems.push(`categories.${RELIEF}: relief is filled by source type, not keywords; remove it from "categories"`);
      } else if (!Array.isArray(keywords) || !keywords.length || !keywords.every((k) => typeof k === 'string' && /[\p{L}\p{N}]/u.test(k))) {
        problems.push(`categories.${name} must be a non-empty list of keywords`);
      }
    }
  }

  if (!Array.isArray(raw.feeds)) problems.push('"feeds" must be a list');
  const feeds = (Array.isArray(raw.feeds) ? raw.feeds : []).map((entry, i) => {
    const where = `feeds[${i}]${typeof entry?.name === 'string' ? ` "${entry.name}"` : ''}`;
    if (!entry || typeof entry !== 'object') {
      problems.push(`${where} must be an object`);
      return null;
    }
    if (typeof entry.name !== 'string' || !entry.name.trim()) problems.push(`${where}: "name" is required`);
    if (!SOURCE_TYPES.includes(entry.type)) problems.push(`${where}: "type" must be one of ${SOURCE_TYPES.join(', ')}`);
    if (entry.handle !== undefined && (typeof entry.handle !== 'string' || !entry.handle.trim())) problems.push(`${where}: "handle" must be a non-empty string`);
    if (entry.enabled !== undefined && typeof entry.enabled !== 'boolean') problems.push(`${where}: "enabled" must be true or false`);
    let xUsername = null;
    if (!isHttpUrl(entry.url)) {
      problems.push(`${where}: "url" must be an http(s) URL`);
    } else if (isXUrl(entry.url)) {
      xUsername = xUsernameFromProfileUrl(entry.url);
      // Disabled entries may hold placeholders; they are checked once enabled.
      if (!xUsername && entry.enabled !== false) problems.push(`${where}: X sources must be profile URLs such as https://x.com/username`);
    }
    return {
      name: String(entry.name ?? '').trim(),
      url: String(entry.url ?? '').trim(),
      type: entry.type,
      handle: entry.handle?.trim() || (xUsername ? `@${xUsername}` : null),
      enabled: entry.enabled !== false,
      xUsername,
    };
  });

  if (problems.length) throw new Error(`${path.basename(file)} has problems:\n  - ${problems.join('\n  - ')}`);
  return { settings, feeds, categories: compileCategories(categories) };
}

// ---------------------------------------------------------------------------
// Keyword matching

/**
 * Turns a keyword from feeds.json into a regular expression. Matching is
 * case-insensitive and on whole words ("rent" does not match "current"), simple
 * plurals are included ("teacher" matches "teachers", "utility" matches
 * "utilities"), a trailing * matches any ending ("arrest*" matches "arrested"),
 * and the words of a phrase may be separated by spaces or hyphens.
 */
function keywordPattern(keyword) {
  let text = normalizeForMatching(keyword.trim());
  const wildcard = text.endsWith('*');
  if (wildcard) text = text.replace(/\*+$/, '');
  const words = text
    .split(/[\s‐‑-]+/)
    .filter(Boolean)
    .map((word) => escapeRegExp(word).replace(/'/g, "['‘’ʼ]")); // straight or curly apostrophes
  let last = words.pop();
  if (wildcard) last += `${WORD_CHAR}*`;
  else if (/[^aeiou]y$/i.test(last)) last = `${last.slice(0, -1)}(?:y|ies)`;
  else if (/\p{L}$/u.test(last)) last += '(?:e?s)?';
  words.push(last);
  return new RegExp(`(?<!${WORD_CHAR})${words.join(PHRASE_GAP)}(?!${WORD_CHAR})`, 'iu');
}

function compileCategories(categories) {
  return Object.entries(categories).map(([name, keywords]) => ({
    name,
    keywords: [...new Set(keywords.map((k) => k.trim()))].map((keyword) => ({ keyword, pattern: keywordPattern(keyword) })),
  }));
}

/**
 * Scores an item against every keyword category: +3 for each keyword found in
 * the title, +1 for each found in the summary, text or tags. The highest score
 * wins; a tie goes to the category listed first in feeds.json. Returns null
 * when nothing matches.
 */
function categorize(item, categories) {
  const title = normalizeForMatching(item.title);
  const body = normalizeForMatching([item.summary, item.content, item.tags.join(' | ')].join('\n'));
  const matches = [];
  for (const category of categories) {
    let score = 0;
    const hits = [];
    for (const { keyword, pattern } of category.keywords) {
      const inTitle = pattern.test(title);
      const inBody = pattern.test(body);
      if (!inTitle && !inBody) continue;
      hits.push(keyword);
      score += (inTitle ? TITLE_WEIGHT : 0) + (inBody ? 1 : 0);
    }
    if (score > 0) matches.push({ name: category.name, score, hits });
  }
  if (!matches.length) return null;
  const best = matches.reduce((a, b) => (b.score > a.score ? b : a));
  return {
    category: best.name,
    matched_keywords: best.hits,
    secondary_categories: matches.filter((m) => m !== best).map((m) => m.name),
  };
}

function normalizeForMatching(text) {
  return (text || '')
    .normalize('NFKC')
    .replace(/[‘’ʼ]/g, "'")
    .replace(/[“”]/g, '"');
}

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ---------------------------------------------------------------------------
// Fetching

async function fetchSource(feed, settings, xAccounts) {
  const started = Date.now();
  try {
    const { items, xCursor = null } = feed.xUsername
      ? await fetchXPosts(feed, settings, xAccounts)
      : { items: await fetchRssItems(feed, settings) };
    return { feed, ok: true, items, xCursor, seconds: (Date.now() - started) / 1000 };
  } catch (err) {
    const error = err instanceof SourceError ? err.message : `unexpected error: ${oneLine(err.message)}`;
    return { feed, ok: false, error, items: [], seconds: (Date.now() - started) / 1000 };
  }
}

async function fetchRssItems(feed, settings) {
  const xml = await download(feed.url, settings, { accept: FEED_ACCEPT });
  try {
    const parsed = await new Parser({ customFields: { item: RSS_ITEM_FIELDS } }).parseString(xml);
    return parsed.items || [];
  } catch (err) {
    throw new SourceError(`malformed or unrecognized feed: ${oneLine(err.message)}`);
  }
}

/** GETs a URL and returns the body as text, turning every kind of failure into a SourceError. */
async function download(url, settings, headers = {}) {
  try {
    const response = await fetch(url, {
      headers: { 'user-agent': settings.user_agent, ...headers },
      redirect: 'follow',
      signal: AbortSignal.timeout(settings.request_timeout_ms),
    });
    if (!response.ok) {
      await response.body?.cancel().catch(() => {});
      throw new SourceError(`HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}`);
    }
    const bytes = await readBody(response);
    return decodeText(bytes, response.headers.get('content-type'));
  } catch (err) {
    if (err instanceof SourceError) throw err;
    if (err.name === 'TimeoutError' || err.name === 'AbortError') {
      throw new SourceError(`timed out after ${settings.request_timeout_ms / 1000}s`);
    }
    const cause = err.cause?.errors?.[0] || err.cause;
    throw new SourceError(`network error: ${oneLine(cause?.message || cause?.code || err.message)}`);
  }
}

async function readBody(response) {
  const tooBig = `response is larger than ${MAX_RESPONSE_BYTES / 1024 / 1024} MB`;
  if (Number(response.headers.get('content-length')) > MAX_RESPONSE_BYTES) {
    await response.body?.cancel().catch(() => {});
    throw new SourceError(tooBig);
  }
  const chunks = [];
  let size = 0;
  for await (const chunk of response.body ?? []) {
    size += chunk.byteLength;
    if (size > MAX_RESPONSE_BYTES) throw new SourceError(tooBig);
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

/** Decodes using the charset from the Content-Type header or the XML declaration, else UTF-8. */
function decodeText(bytes, contentType) {
  let charset = null;
  for (const param of (contentType || '').split(';').slice(1)) {
    const [key, value] = param.split('=');
    if (key.trim().toLowerCase() === 'charset' && value) charset = value.trim().replace(/^["']|["']$/g, '');
  }
  if (!charset && bytes[0] === 0xff && bytes[1] === 0xfe) charset = 'utf-16le';
  if (!charset && bytes[0] === 0xfe && bytes[1] === 0xff) charset = 'utf-16be';
  if (!charset) {
    const declaration = /^\s*<\?xml[^>]*?\sencoding\s*=\s*["']([\w.:-]+)["']/.exec(bytes.subarray(0, 200).toString('latin1'));
    if (declaration) charset = declaration[1];
  }
  try {
    return new TextDecoder(charset || 'utf-8').decode(bytes);
  } catch {
    return new TextDecoder('utf-8').decode(bytes); // unknown charset label
  }
}

// ---------------------------------------------------------------------------
// X accounts (X API v2)

function isXUrl(url) {
  try {
    return X_LINK_HOSTS.has(new URL(url).hostname.toLowerCase());
  } catch {
    return false;
  }
}

function xUsernameFromProfileUrl(url) {
  const { hostname, pathname } = new URL(url);
  if (!X_HOSTS.has(hostname.toLowerCase())) return null;
  const match = /^\/@?(\w{1,15})\/?$/.exec(pathname);
  return match ? match[1] : null;
}

/** Reads an account's recent original posts (no reposts or replies) newer than the last run's. */
async function fetchXPosts(feed, settings, xAccounts) {
  const token = process.env.X_BEARER_TOKEN;
  if (!token) throw new SourceError('X_BEARER_TOKEN is not set; it is needed to read X accounts');
  const key = feed.xUsername.toLowerCase();
  const known = xAccounts.get(key);
  let userId = known?.user_id;
  if (!userId) {
    const user = await xApiGet(`/2/users/by/username/${encodeURIComponent(feed.xUsername)}`, token, settings);
    userId = user.data.id;
  }
  const params = new URLSearchParams({
    max_results: String(settings.x_max_posts),
    exclude: 'retweets,replies',
    'tweet.fields': 'created_at,entities,note_tweet',
  });
  if (known?.newest_post_id) params.set('since_id', known.newest_post_id);
  const timeline = await xApiGet(`/2/users/${encodeURIComponent(userId)}/tweets?${params}`, token, settings);
  return {
    items: (timeline.data || []).map((post) => xPostToItem(post, feed.xUsername)),
    xCursor: { username: key, user_id: userId, newest_post_id: timeline.meta?.newest_id || known?.newest_post_id || null },
  };
}

async function xApiGet(apiPath, token, settings) {
  let body;
  try {
    const base = process.env.X_API_BASE_URL || 'https://api.x.com';
    body = await download(`${base}${apiPath}`, settings, { authorization: `Bearer ${token}`, accept: 'application/json' });
  } catch (err) {
    const hint = { 401: 'check X_BEARER_TOKEN', 403: 'your X API access level may not allow reading posts', 429: 'rate limited, try again later' }[
      /^HTTP (\d+)/.exec(err.message)?.[1]
    ];
    throw hint ? new SourceError(`X API ${err.message} (${hint})`) : err;
  }
  let json;
  try {
    json = JSON.parse(body);
  } catch {
    throw new SourceError('X API returned a response that is not JSON');
  }
  if (!json.data && json.errors?.length) throw new SourceError(`X API: ${json.errors[0].detail || json.errors[0].title}`);
  return json;
}

/** Shapes an X post like an rss-parser item so both kinds of source flow through the same code. */
function xPostToItem(post, username) {
  const long = post.note_tweet; // posts over 280 characters carry their full text here
  const urls = (long?.entities || post.entities)?.urls || [];
  let text = long?.text || post.text || '';
  for (const u of urls) {
    const target = u.unwound_url || u.expanded_url;
    text = text.split(u.url).join(isXUrl(target) ? '' : target || u.url);
  }
  text = text.trim();
  const related = urls.map((u) => u.unwound_url || u.expanded_url).filter((u) => isHttpUrl(u) && !isXUrl(u));
  return {
    title: firstLine(text.replace(/https?:\/\/\S+/g, '').replace(/[ \t]+/g, ' '), 140),
    link: `https://x.com/${username}/status/${post.id}`,
    guid: `x:${post.id}`,
    pubDate: post.created_at,
    isoDate: post.created_at,
    contentSnippet: text,
    creator: `@${username}`,
    relatedLinks: [...new Set(related)],
  };
}

function firstLine(text, maxLength) {
  const line = text.split('\n').find((l) => l.trim()) || '';
  if (line.length <= maxLength) return line.trim();
  const cut = line.slice(0, maxLength);
  return `${cut.slice(0, cut.lastIndexOf(' ') > 40 ? cut.lastIndexOf(' ') : maxLength).trim()}…`;
}

// ---------------------------------------------------------------------------
// Items

function toText(value) {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  if (typeof value === 'object' && typeof value._ === 'string') return value._;
  return '';
}

/** Collapses runs of spaces and blank lines left over from HTML. */
function tidy(value) {
  return toText(value)
    .replace(/\r\n?/g, '\n')
    .replace(/[^\S\n]+/g, ' ')
    .replace(/ ?\n ?/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/** Resolves a link against the feed URL and keeps it only if it is http(s). */
function safeLink(value, base) {
  const text = toText(value).trim();
  if (!text) return null;
  try {
    const url = new URL(text, base);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null;
  } catch {
    return null;
  }
}

/** The form of a link used to spot the same story in two places: no #fragment, no tracking parameters. */
function linkKey(link) {
  const url = new URL(link);
  url.hash = '';
  for (const key of [...url.searchParams.keys()]) {
    if (/^utm_/i.test(key) || ['fbclid', 'gclid', 'mc_cid', 'mc_eid'].includes(key.toLowerCase())) url.searchParams.delete(key);
  }
  return url.href;
}

function normalizeItem(raw, feed, fetchedAt) {
  const title = tidy(raw.titleTextSnippet || raw.title);
  const link = safeLink(raw.link, feed.url);
  const guid = tidy(raw.guid || raw.id) || null;
  const pubDate = tidy(raw.pubDate || raw.date) || null;
  const videoDescription = raw.mediaGroup ? tidy(raw.mediaGroup['media:description']?.[0]) : '';
  const summary = tidy(raw.summaryTextSnippet || raw.contentSnippet) || videoDescription;
  const content = tidy(raw['content:encodedSnippet'] || raw.contentSnippet || raw.summaryTextSnippet) || videoDescription;
  const tags = (Array.isArray(raw.categories) ? raw.categories : []).map(tidy).filter(Boolean);
  const identity = guid ? `guid:${guid}` : link ? `link:${linkKey(link)}` : `text:${title}|${pubDate}`;
  return {
    id: crypto.createHash('sha256').update(`${feed.url}\n${identity}`).digest('hex').slice(0, 16),
    title,
    link,
    related_links: (raw.relatedLinks || []).filter(isHttpUrl),
    pubDate,
    isoDate: raw.isoDate || null,
    author: tidy(raw.creator || raw.author) || null,
    source_name: feed.name,
    source_type: feed.type,
    source_handle: feed.handle,
    feed_url: feed.url,
    summary,
    content,
    tags,
    guid,
    fetched_at: fetchedAt,
  };
}

// ---------------------------------------------------------------------------
// Pending batch

function newBatch(now, categories) {
  const stamp = now.toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
  return {
    batch_id: `${stamp}-${crypto.randomBytes(3).toString('hex')}`,
    batch_started_at: now.toISOString(),
    updated_at: now.toISOString(),
    categories,
  };
}

function checkPendingShape(pending, file) {
  const ok =
    pending &&
    typeof pending.batch_id === 'string' &&
    pending.categories &&
    typeof pending.categories === 'object' &&
    Object.values(pending.categories).every(Array.isArray);
  if (!ok) throw new Error(`${path.basename(file)} is not in the expected format; move it aside and run again`);
}

/**
 * Continues the current batch, or starts a new one once draft_entries.json shows
 * the current batch drafted and every draft reviewed. Items queued after the
 * drafts were written (not in covered_item_ids) move into the new batch.
 */
function openBatch(pending, drafts, categoryNames, now) {
  let batch = pending;
  const reviewed = drafts && Object.values(drafts.entries || {}).every((entry) => entry?.review);
  if (batch && drafts && drafts.source_batch_id === batch.batch_id && reviewed) {
    const covered = new Set(drafts.covered_item_ids || []);
    const carried = Object.fromEntries(
      Object.entries(batch.categories).map(([name, items]) => [name, items.filter((item) => !covered.has(item.id))]),
    );
    batch = { ...newBatch(now, carried), previous_batch_id: pending.batch_id };
  }
  batch ??= newBatch(now, {});
  for (const name of [...categoryNames, RELIEF]) batch.categories[name] ??= [];
  return batch;
}

// ---------------------------------------------------------------------------
// Seen-items database

function openSeenDb(file) {
  const db = new Database(file);
  db.exec(`
    CREATE TABLE IF NOT EXISTS seen_items (
      id            TEXT PRIMARY KEY,  -- hash of the source URL + the item's guid (or link)
      feed_url      TEXT NOT NULL,
      guid          TEXT,
      link          TEXT,              -- link without #fragment or tracking parameters
      category      TEXT,              -- NULL when the item matched no category and was discarded
      first_seen_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS seen_items_link ON seen_items (link);
    CREATE TABLE IF NOT EXISTS x_accounts (
      username       TEXT PRIMARY KEY,  -- lower-cased X handle
      user_id        TEXT NOT NULL,
      newest_post_id TEXT               -- only posts newer than this are requested next time
    );
  `);
  return db;
}

function rememberSeen(db, records, xCursors) {
  const insertSeen = db.prepare(`
    INSERT OR IGNORE INTO seen_items (id, feed_url, guid, link, category, first_seen_at)
    VALUES (@id, @feed_url, @guid, @link, @category, @first_seen_at)`);
  const upsertCursor = db.prepare(`
    INSERT INTO x_accounts (username, user_id, newest_post_id) VALUES (@username, @user_id, @newest_post_id)
    ON CONFLICT (username) DO UPDATE SET user_id = excluded.user_id, newest_post_id = excluded.newest_post_id`);
  db.transaction(() => {
    for (const record of records) insertSeen.run(record);
    for (const cursor of xCursors) upsertCursor.run(cursor);
  })();
}

// ---------------------------------------------------------------------------
// Run

/**
 * Files every item of the fetched sources: duplicates are counted and dropped,
 * new items are categorized and appended to the batch. Returns the per-source
 * statistics and the records to store in seen_items.db.
 */
function fileItems(results, batch, db, categories, fetchedAt, log) {
  const alreadySeen = db.prepare('SELECT 1 FROM seen_items WHERE id = ? OR link = ? LIMIT 1');
  const queued = new Map(Object.values(batch.categories).flat().map((item) => [item.id, item.category]));
  const idsThisRun = new Set();
  const linksThisRun = new Set();
  const seenRecords = [];
  const perSource = [];
  const filedByCategory = Object.fromEntries(Object.keys(batch.categories).map((name) => [name, 0]));

  for (const result of results) {
    const { feed } = result;
    const stats = { feed, ok: result.ok, error: result.error, seconds: result.seconds, fetched: 0, duplicates: 0, new: 0, matched: 0, discarded: 0, skipped: 0 };
    perSource.push(stats);
    for (const raw of result.items) {
      stats.fetched++;
      let item;
      try {
        item = normalizeItem(raw, feed, fetchedAt);
      } catch (err) {
        stats.skipped++;
        log.warn(`  ${feed.name}: skipped an item that could not be read (${oneLine(err.message)})`);
        continue;
      }
      const key = item.link ? linkKey(item.link) : null;
      const record = { id: item.id, feed_url: feed.url, guid: item.guid, link: key, category: null, first_seen_at: fetchedAt };
      if (queued.has(item.id)) {
        // Already waiting in this batch; make sure the database knows it too.
        seenRecords.push({ ...record, category: queued.get(item.id) });
        stats.duplicates++;
        continue;
      }
      if (idsThisRun.has(item.id) || (key && linksThisRun.has(key)) || alreadySeen.get(item.id, key)) {
        stats.duplicates++;
        continue;
      }
      idsThisRun.add(item.id);
      if (key) linksThisRun.add(key);
      stats.new++;

      const filing =
        feed.type === RELIEF
          ? { category: RELIEF, matched_keywords: [], secondary_categories: [] }
          : categorize(item, categories);
      seenRecords.push({ ...record, category: filing?.category ?? null });
      if (!filing) {
        stats.discarded++;
        continue;
      }
      stats.matched++;
      filedByCategory[filing.category]++;
      batch.categories[filing.category].push({ id: item.id, category: filing.category, ...item, ...filing });
    }
  }
  return { perSource, seenRecords, filedByCategory };
}

async function run(options = {}) {
  const files = { ...PATHS, ...options.files };
  const log = options.log || console;
  const now = options.now || new Date();
  const config = loadConfig(files.config);

  // Refuse to start if the pending file is unreadable: it may hold items that
  // were never drafted, so it must not be replaced.
  const pending = readJsonFile(files.pending);
  if (pending) checkPendingShape(pending, files.pending);
  let drafts = null;
  try {
    drafts = readJsonFile(files.drafts);
  } catch (err) {
    log.warn(`Warning: ignoring ${path.basename(files.drafts)} (${err.message}); new items join the current batch.`);
  }
  const batch = openBatch(pending, drafts, config.categories.map((c) => c.name), now);
  if (pending && batch.batch_id !== pending.batch_id) {
    log.info(`Batch ${pending.batch_id} has been drafted and reviewed; starting batch ${batch.batch_id}.`);
  }

  const db = openSeenDb(files.seenDb);
  try {
    const xAccounts = new Map(db.prepare('SELECT * FROM x_accounts').all().map((row) => [row.username, row]));
    const enabled = config.feeds.filter((feed) => feed.enabled);
    const disabled = config.feeds.filter((feed) => !feed.enabled);
    const { request_timeout_ms: timeout, concurrency } = config.settings;
    log.info(`Fetching ${enabled.length} source(s), ${concurrency} at a time, ${timeout / 1000}s timeout each...`);

    const results = await mapLimit(enabled, concurrency, async (feed) => {
      const result = await fetchSource(feed, config.settings, xAccounts);
      if (result.ok) log.info(`  ok    ${feed.name}: ${result.items.length} item(s) in ${result.seconds.toFixed(1)}s`);
      else log.error(`  FAIL  ${feed.name}: ${result.error}`);
      return result;
    });

    const fetchedAt = now.toISOString();
    const { perSource, seenRecords, filedByCategory } = fileItems(results, batch, db, config.categories, fetchedAt, log);
    batch.updated_at = fetchedAt;

    // Write the queue first, then mark items as seen: if the run dies in between,
    // the items are fetched again next time instead of being lost.
    writeJsonAtomic(files.pending, batch);
    const xCursors = results.filter((r) => r.ok && r.xCursor).map((r) => r.xCursor);
    rememberSeen(db, seenRecords, xCursors);

    const summary = { batch, perSource, filedByCategory, disabled };
    printSummary(summary, files, log);
    return summary;
  } finally {
    db.close();
  }
}

// ---------------------------------------------------------------------------
// Summary

function printSummary({ batch, perSource, filedByCategory, disabled }, files, log) {
  const header = ['Source', 'Type', 'Fetched', 'Duplicates', 'New', 'Matched', 'Discarded', 'Status'];
  const rows = perSource.map((s) => [
    truncate(s.feed.name, 36),
    s.feed.type,
    ...(s.ok ? [s.fetched, s.duplicates, s.new, s.matched, s.discarded] : ['-', '-', '-', '-', '-']),
    s.ok ? (s.skipped ? `ok, ${s.skipped} unreadable item(s) skipped` : 'ok') : `FAILED: ${s.error}`,
  ]);
  const ok = perSource.filter((s) => s.ok);
  const total = (key) => ok.reduce((sum, s) => sum + s[key], 0);
  rows.push([`TOTAL (${ok.length} of ${perSource.length} ok)`, '', total('fetched'), total('duplicates'), total('new'), total('matched'), total('discarded'), '']);

  const widths = header.map((h, col) => Math.max(h.length, ...rows.map((row) => String(row[col]).length)));
  const numeric = new Set([2, 3, 4, 5, 6]);
  const line = (row) =>
    row
      .map((cell, col) => (col === row.length - 1 ? String(cell) : numeric.has(col) ? String(cell).padStart(widths[col]) : String(cell).padEnd(widths[col])))
      .join('  ')
      .trimEnd();

  const rule = widths.map((w, col) => '-'.repeat(col === widths.length - 1 ? 6 : w)).join('  ');
  log.info('');
  log.info('Summary');
  log.info(line(header));
  log.info(rule);
  rows.slice(0, -1).forEach((row) => log.info(line(row)));
  log.info(rule);
  log.info(line(rows[rows.length - 1]));
  log.info('Matched = filed under a category (relief sources skip keyword matching; all their new items are filed under relief).');

  log.info(`Filed this run: ${Object.entries(filedByCategory).map(([name, n]) => `${name} ${n}`).join(', ')}`);
  if (disabled.length) log.info(`Disabled in feeds.json (not fetched): ${disabled.map((f) => f.name).join(', ')}`);
  const queuedTotal = Object.values(batch.categories).reduce((sum, items) => sum + items.length, 0);
  log.info(`${path.basename(files.pending)} now holds ${queuedTotal} item(s) in batch ${batch.batch_id}.`);
}

function truncate(text, max) {
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}

function oneLine(text) {
  return String(text).replace(/\s+/g, ' ').trim();
}

// ---------------------------------------------------------------------------

async function main() {
  console.log(`MD Watch: fetching sources (${new Date().toISOString()})`);
  try {
    loadEnvFile();
    await withLock(PATHS.fetchLock, 'fetch_feeds.js', () => run());
  } catch (err) {
    console.error(`\nfetch_feeds.js stopped: ${err.message}`);
    process.exitCode = 1;
  }
}

if (require.main === module) main();

module.exports = { run, loadConfig, keywordPattern, categorize, normalizeItem, xPostToItem, openBatch, decodeText, SOURCE_TYPES };
