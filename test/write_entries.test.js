'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { run, draftGate } = require('../write_entries');
const { COMMENTARY_LINE, quoteAppearsIn } = require('../lib/entries');
const { fakeClaude } = require('./helpers/fake_claude');

const quiet = { info() {}, warn() {}, error() {} };

function item(id, category, source_type, title, extra = {}) {
  return {
    id,
    category,
    title,
    link: `https://example.test/${id}`,
    related_links: [],
    pubDate: 'Sat, 26 Sep 2026 14:00:00 -0400',
    isoDate: '2026-09-26T18:00:00.000Z',
    author: null,
    source_name: `${source_type} source`,
    source_type,
    source_handle: null,
    summary: `${title}. More detail here for readers.`,
    content: `${title}. More detail here for readers.`,
    tags: [],
    matched_keywords: category === 'relief' ? [] : ['keyword'],
    secondary_categories: [],
    ...extra,
  };
}

function pendingBatch() {
  return {
    batch_id: 'batch-1',
    categories: {
      politicians: [
        item('p1', 'politicians', 'news_org', 'Governor signs the state budget', { author: 'Jane Reporter' }),
        item('p2', 'politicians', 'campaign_official', 'We will cut your taxes and fix the roads', {
          author: '@TestCampaign',
          link: 'https://x.com/TestCampaign/status/9002',
          related_links: ['https://example.test/plan'],
        }),
        item('p3', 'politicians', 'reporter', 'Council race heats up in District 12'),
        item('p4', 'politicians', 'news_org', 'Old story that was taken down'),
        item('p5', 'politicians', 'news_org', 'Item without a link', { link: null }),
      ],
      crime: [],
      education: [],
      cost_of_living: [
        item('c1', 'cost_of_living', 'citizen_commentary', 'Water bill doubled and nobody at City Hall will explain why', { author: '/u/crabcakefan' }),
        item('c2', 'cost_of_living', 'independent', 'Rents are up again in Remington', { source_handle: '@RemingtonNews' }),
      ],
      relief: [
        item('r1', 'relief', 'relief', 'Corgi meets snow for the first time', { source_handle: '@HappyPups' }),
        item('r2', 'relief', 'relief', 'I told strangers their dog was famous and they believed me', { source_handle: '@PrankGuy' }),
        item('r3', 'relief', 'relief', 'Goat escapes petting zoo, visits bakery', { source_handle: '@HappyPups' }),
      ],
    },
  };
}

function setup(pending = pendingBatch()) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mdwatch-write-'));
  const files = {
    pending: path.join(dir, 'pending_items.json'),
    drafts: path.join(dir, 'draft_entries.json'),
    publishedLog: path.join(dir, 'published_log.json'),
  };
  fs.writeFileSync(files.pending, JSON.stringify(pending));
  return files;
}

// Every link answers except the one for p4, which is gone.
const checkLink = async (url) => (url.endsWith('/p4') ? { status: 'broken', detail: 'HTTP 404' } : { status: 'ok' });

test('writes one entry per category with the required highlight formats, links and relief setup', async () => {
  const files = setup();
  const client = fakeClaude();
  const { drafts } = await run({ files, client, checkLink, log: quiet });

  assert.deepEqual(Object.keys(drafts.entries), ['politicians', 'cost_of_living', 'relief']);
  assert.equal(drafts.source_batch_id, 'batch-1');
  assert.deepEqual(drafts.covered_item_ids.sort(), ['c1', 'c2', 'p1', 'p2', 'p3', 'p4', 'p5', 'r1', 'r2', 'r3']);

  const politics = drafts.entries.politicians;
  assert.match(politics.inference_paragraph, /^Politicians\? Heating up\./);
  assert.ok(!('setup_line' in politics));
  assert.equal(politics.review, null);
  assert.deepEqual(politics.left_out.map((i) => [i.item_id, i.reason]), [
    ['p4', 'link is broken (HTTP 404)'],
    ['p5', 'no link to the original post'],
  ]);
  assert.ok(politics.highlights.length >= 2 && politics.highlights.length <= 3);

  for (const entry of Object.values(drafts.entries)) {
    for (const h of entry.highlights) {
      assert.match(h.link, /^https?:\/\//, 'every highlight links to the original post');
      if (h.format === 'quote') {
        assert.equal(h.context_line, COMMENTARY_LINE);
        assert.equal(h.headline, `"${h.quote}" —${h.handle}`);
        assert.ok(quoteAppearsIn(h.quote, h.post_text), 'quotes are taken from the post');
      } else {
        assert.notEqual(h.context_line, COMMENTARY_LINE);
      }
    }
  }

  // Source type decides the format for civic items.
  const byItem = Object.fromEntries(Object.values(drafts.entries).flatMap((e) => e.highlights).map((h) => [h.item_id, h]));
  assert.equal(byItem.p1.format, 'headline');
  assert.equal(byItem.p2.format, 'quote');
  assert.equal(byItem.p2.handle, '@TestCampaign');
  assert.deepEqual(byItem.p2.related_links, ['https://example.test/plan']);
  assert.equal(byItem.c1.handle, '@crabcakefan');
  assert.equal(byItem.c2.handle, '@RemingtonNews');

  // Relief: a one-line setup instead of a synthesis; neutral clips get headlines, the prank creator's own framing a quote.
  const relief = drafts.entries.relief;
  assert.ok(!('inference_paragraph' in relief));
  assert.ok(relief.setup_line && !relief.setup_line.includes('\n'));
  assert.equal(byItem.r1.format, 'headline');
  assert.match(byItem.r1.context_line, /@HappyPups/);
  assert.equal(byItem.r2.format, 'quote');
  assert.equal(byItem.r2.context_line, COMMENTARY_LINE);

  // How Claude is called.
  const request = client.requests[0];
  assert.equal(request.model, 'claude-opus-5');
  assert.equal(request.output_config.format.type, 'json_schema');
  assert.equal(request.fallbacks, 'default');
  assert.deepEqual(request.betas, ['server-side-fallback-2026-07-01']);
  assert.match(request.system, /not a fact-checker/);
  assert.ok(!request.messages[0].content.includes('https://'), 'links are never sent to (or taken from) the model');

  assert.ok(!fs.existsSync(files.publishedLog), 'drafting never touches published_log.json');
});

test('a quote that is not word for word gets one retry with the problem spelled out', async () => {
  const files = setup();
  const client = fakeClaude({ misquoteFirst: ['Cost of Living'] });
  const { drafts } = await run({ files, client, checkLink, log: quiet });
  const costRequests = client.requests.filter((r) => r.messages[0].content.startsWith('Section: Cost of Living'));
  assert.equal(costRequests.length, 2);
  assert.match(costRequests[1].messages[0].content, /not copied word for word/);
  assert.deepEqual(drafts.entries.cost_of_living.review_flags, []);
});

test('when Claude declines a section, the entry is filled in mechanically and flagged', async () => {
  const files = setup();
  const { drafts } = await run({ files, client: fakeClaude({ refuse: ['Relief'] }), checkLink, log: quiet });
  const relief = drafts.entries.relief;
  assert.ok(relief.setup_line);
  assert.ok(relief.highlights.length >= 2);
  assert.match(relief.review_flags.join(' '), /declined/);
});

test('drafts are only rewritten when that cannot lose a review', () => {
  const pending = { batch_id: 'b2' };
  const entries = (...reviews) => Object.fromEntries(reviews.map((review, i) => [`c${i}`, { review }]));
  assert.equal(draftGate(null, pending), null);
  assert.equal(draftGate({ source_batch_id: 'b2', entries: entries(null, null) }, pending), null);
  assert.match(draftGate({ source_batch_id: 'b2', entries: entries({ decision: 'approved' }, null) }, pending), /under way/);
  assert.match(draftGate({ source_batch_id: 'b2', entries: entries({ decision: 'skipped' }) }, pending), /already been drafted and reviewed/);
  assert.match(draftGate({ source_batch_id: 'b1', entries: entries(null) }, pending), /unreviewed entr/);
  assert.equal(draftGate({ source_batch_id: 'b1', entries: entries({ decision: 'approved' }) }, pending), null);
});
