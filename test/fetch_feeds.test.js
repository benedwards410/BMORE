'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { run, loadConfig, keywordPattern, categorize, openBatch } = require('../fetch_feeds');
const { startFixtureServer, X_TOKEN } = require('./helpers/fixture_server');

const quiet = { info() {}, warn() {}, error() {} };
const realConfig = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'feeds.json'), 'utf8'));

function tempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'mdwatch-fetch-'));
}

function filesIn(dir) {
  return {
    config: path.join(dir, 'feeds.json'),
    seenDb: path.join(dir, 'seen_items.db'),
    pending: path.join(dir, 'pending_items.json'),
    drafts: path.join(dir, 'draft_entries.json'),
  };
}

function writeConfig(dir, feeds, settings = { request_timeout_ms: 1000, concurrency: 4 }) {
  fs.writeFileSync(path.join(dir, 'feeds.json'), JSON.stringify({ settings, feeds, categories: realConfig.categories }));
}

test('keywords match whole words, simple plurals, wildcards and hyphenated phrases', () => {
  const matches = (keyword, text) => keywordPattern(keyword).test(text);
  assert.ok(matches('teacher', 'Teachers rally in Annapolis'));
  assert.ok(matches('utility', 'Utilities want another rate increase'));
  assert.ok(matches('tax', 'New taxes on the table'));
  assert.ok(!matches('tax', 'Taxi drivers protest'));
  assert.ok(matches('rent*', 'Rental prices climb'));
  assert.ok(!matches('rent*', 'The current plan'));
  assert.ok(matches('arrest*', 'Two arrested after chase'));
  assert.ok(matches('cost of living', 'A cost-of-living crunch'));
  assert.ok(matches("state's attorney", 'The state’s attorney declined to comment'));
  assert.ok(matches('pre-K', 'Pre K expansion stalls'));
});

test('an item goes to its highest-scoring category; titles count triple and ties go to the first category', () => {
  const { categories } = loadConfig(path.join(__dirname, '..', 'feeds.json'));
  const item = (title, body = '') => ({ title, summary: body, content: body, tags: [] });

  const tie = categorize(item('Mayor visits school'), categories);
  assert.equal(tie.category, 'politicians');
  assert.deepEqual(tie.secondary_categories, ['education']);

  const titleWins = categorize(item('Police arrest suspect', 'The mayor spoke at the scene.'), categories);
  assert.equal(titleWins.category, 'crime');
  assert.deepEqual(titleWins.matched_keywords, ['police', 'arrest*', 'suspect*']);

  assert.equal(categorize(item('Orioles walk off in the 11th'), categories), null);
});

test('config problems are reported together and stop the run', () => {
  const dir = tempDir();
  fs.writeFileSync(
    path.join(dir, 'feeds.json'),
    JSON.stringify({
      feeds: [
        { name: 'A', url: 'not a url', type: 'news_org' },
        { name: 'B', url: 'https://example.test/feed', type: 'blog' },
        { name: 'C', url: 'https://x.com/REPLACE-WITH-HANDLE', type: 'relief' },
      ],
      categories: { relief: ['dog'], crime: [] },
    }),
  );
  assert.throws(() => loadConfig(path.join(dir, 'feeds.json')), (err) => {
    for (const expected of ['"url" must be an http(s) URL', '"type" must be one of', 'X sources must be profile URLs', 'relief is filled by source type', 'categories.crime']) {
      assert.match(err.message, new RegExp(expected.replace(/[()"]/g, '.')));
    }
    return true;
  });
});

test('fetches every source, survives failing ones, files items by category and remembers them', async (t) => {
  const server = await startFixtureServer();
  t.after(() => server.close());
  process.env.X_API_BASE_URL = server.base;
  process.env.X_BEARER_TOKEN = X_TOKEN;
  t.after(() => {
    delete process.env.X_API_BASE_URL;
    delete process.env.X_BEARER_TOKEN;
  });

  const { base } = server;
  const dir = tempDir();
  writeConfig(dir, [
    { name: 'Chesapeake Ledger', url: `${base}/news.xml`, type: 'news_org' },
    { name: 'r/testbaltimore', url: `${base}/commentary.xml`, type: 'citizen_commentary' },
    { name: 'Happy Pups', url: `${base}/relief.xml`, type: 'relief', handle: '@HappyPups' },
    { name: 'Wire copy', url: `${base}/dup.xml`, type: 'news_org' },
    { name: 'Café Gazette', url: `${base}/latin1.xml`, type: 'independent' },
    { name: 'Redirected pups', url: `${base}/redirect.xml`, type: 'relief' },
    { name: 'Test Campaign', url: 'https://x.com/TestCampaign', type: 'campaign_official' },
    { name: 'Test Dogs', url: 'https://x.com/TestDogs', type: 'relief' },
    { name: 'Missing', url: `${base}/missing.xml`, type: 'news_org' },
    { name: 'Hangs', url: `${base}/hang.xml`, type: 'reporter' },
    { name: 'Stalls', url: `${base}/stall.xml`, type: 'reporter' },
    { name: 'Broken XML', url: `${base}/broken.xml`, type: 'independent' },
    { name: 'HTML page', url: `${base}/page.html`, type: 'independent' },
    { name: 'Huge', url: `${base}/huge.xml`, type: 'independent' },
    { name: 'Template', url: 'https://x.com/REPLACE-WITH-HANDLE', type: 'reporter', enabled: false },
  ]);
  const files = filesIn(dir);

  const first = await run({ files, log: quiet });
  const status = Object.fromEntries(first.perSource.map((s) => [s.feed.name, s.ok ? 'ok' : s.error]));
  assert.equal(status['Missing'], 'HTTP 404 Not Found');
  assert.equal(status['Hangs'], 'timed out after 1s');
  assert.equal(status['Stalls'], 'timed out after 1s');
  assert.match(status['Broken XML'], /^malformed or unrecognized feed/);
  assert.match(status['HTML page'], /^malformed or unrecognized feed/);
  assert.match(status['Huge'], /larger than 10 MB/);
  assert.ok(!('Template' in status), 'disabled sources are not fetched');
  for (const name of ['Chesapeake Ledger', 'r/testbaltimore', 'Happy Pups', 'Wire copy', 'Café Gazette', 'Test Campaign', 'Test Dogs']) {
    assert.equal(status[name], 'ok', name);
  }

  const pending = JSON.parse(fs.readFileSync(files.pending, 'utf8'));
  assert.deepEqual(Object.keys(pending.categories), ['politicians', 'crime', 'education', 'cost_of_living', 'relief']);
  const all = Object.values(pending.categories).flat();
  for (const item of all) {
    assert.ok(item.source_name && item.source_type, 'every item keeps its source name and type');
    assert.ok(['title', 'link', 'pubDate', 'summary', 'content'].every((key) => key in item));
  }

  // Relief sources bypass keyword matching: the dog story that mentions police stays in relief.
  const relief = pending.categories.relief;
  assert.equal(relief.length, 4);
  assert.ok(relief.every((item) => item.source_type === 'relief' && item.matched_keywords.length === 0));
  assert.ok(relief.some((item) => /police officer/.test(item.title)));
  assert.ok(!pending.categories.crime.some((item) => item.source_type === 'relief'));

  // Items that match no category are discarded, not stored.
  assert.ok(!all.some((item) => /Orioles|crab cakes/.test(item.title)));

  // The same story under a tracking-parameter link, and a repeat inside one feed, are duplicates.
  const wire = first.perSource.find((s) => s.feed.name === 'Wire copy');
  assert.deepEqual([wire.fetched, wire.duplicates, wire.new], [3, 2, 1]);
  assert.equal(first.perSource.find((s) => s.feed.name === 'Redirected pups').duplicates, 3);

  // Charset from the XML declaration; relative links resolved; javascript: links dropped.
  assert.ok(all.some((item) => item.title === 'Café owners protest property tax hike'));
  assert.ok(all.some((item) => item.link === `${base}/articles/relative-overtime`));
  assert.equal(all.find((item) => item.title === 'Link-less mayor item').link, null);

  // X posts: full text of long posts, t.co links expanded, outbound article kept as a related link.
  const homes = all.find((item) => item.guid === 'x:9003');
  assert.equal(homes.link, 'https://x.com/TestCampaign/status/9003');
  assert.deepEqual(homes.related_links, [`${base}/articles/affordable-homes`]);
  assert.equal(homes.author, '@TestCampaign');
  assert.ok(all.find((item) => item.guid === 'x:9002').content.endsWith('exactly what I will fight for.'));

  // Second run: everything is a duplicate, and X is only asked for newer posts.
  const second = await run({ files, log: quiet });
  const totals = second.perSource.filter((s) => s.ok).reduce((sum, s) => ({ new: sum.new + s.new, dup: sum.dup + s.duplicates }), { new: 0, dup: 0 });
  assert.equal(totals.new, 0);
  assert.ok(totals.dup > 0);
  assert.equal(Object.values(JSON.parse(fs.readFileSync(files.pending, 'utf8')).categories).flat().length, all.length);
  assert.ok(server.hits.some((hit) => hit.includes('/2/users/501/tweets') && hit.includes('since_id=9003')));
});

test('a new batch starts once the drafts of the current one are all reviewed, carrying over what they missed', () => {
  const now = new Date('2026-09-27T12:00:00Z');
  const pending = {
    batch_id: 'b1',
    categories: { crime: [{ id: 'drafted' }, { id: 'late' }], relief: [] },
  };
  const unreviewed = { source_batch_id: 'b1', covered_item_ids: ['drafted'], entries: { crime: { review: null } } };
  assert.equal(openBatch(pending, unreviewed, ['crime'], now).batch_id, 'b1');

  const reviewed = { ...unreviewed, entries: { crime: { review: { decision: 'approved' } } } };
  const next = openBatch(pending, reviewed, ['crime'], now);
  assert.notEqual(next.batch_id, 'b1');
  assert.equal(next.previous_batch_id, 'b1');
  assert.deepEqual(next.categories.crime, [{ id: 'late' }]);
});

test('refuses to run when pending_items.json is unreadable, and leaves it alone', async () => {
  const dir = tempDir();
  writeConfig(dir, [{ name: 'Nowhere', url: 'http://127.0.0.1:59999/feed.xml', type: 'news_org' }]);
  const files = filesIn(dir);
  fs.writeFileSync(files.pending, '{ not json');
  await assert.rejects(run({ files, log: quiet }), /pending_items\.json is not valid JSON/);
  assert.equal(fs.readFileSync(files.pending, 'utf8'), '{ not json');
});
