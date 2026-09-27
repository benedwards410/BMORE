'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { run, appendToPublishedLog } = require('../publish_review');
const { COMMENTARY_LINE } = require('../lib/entries');

function tempFiles() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mdwatch-review-'));
  return { dir, drafts: path.join(dir, 'draft_entries.json'), publishedLog: path.join(dir, 'published_log.json') };
}

function entry(category, extra = {}) {
  return {
    category,
    draft_id: `batch-1:${category}`,
    item_count: 2,
    inference_paragraph: 'Put together, these suggest pressure is building. Side by side, they point one way.',
    highlights: [
      {
        headline: 'COUNCIL BLINKS — AGAIN?',
        context_line: 'Chesapeake Ledger reports the council delayed the vote.',
        link: 'https://example.test/a',
        format: 'headline',
        source_name: 'Chesapeake Ledger',
        source_type: 'news_org',
        item_id: `${category}-a`,
        link_check: 'ok',
      },
      {
        headline: '"Nobody at City Hall will explain why" —@crabcakefan',
        context_line: COMMENTARY_LINE,
        link: 'https://example.test/b',
        format: 'quote',
        source_name: 'r/baltimore',
        source_type: 'citizen_commentary',
        item_id: `${category}-b`,
        link_check: 'ok',
        quote: 'Nobody at City Hall will explain why',
        handle: '@crabcakefan',
        post_text: 'Water bill doubled. Nobody at City Hall will explain why rates keep climbing.',
      },
    ],
    sources: [
      { item_id: `${category}-a`, title: 'Council delays vote', source_name: 'Chesapeake Ledger', source_type: 'news_org', link: 'https://example.test/a', link_check: 'ok' },
      { item_id: `${category}-b`, title: 'Water bill doubled', source_name: 'r/baltimore', source_type: 'citizen_commentary', link: 'https://example.test/b', link_check: 'ok' },
    ],
    left_out: [],
    review_flags: [],
    markdown: '',
    review: null,
    ...extra,
  };
}

function writeDrafts(files, entries) {
  fs.writeFileSync(files.drafts, JSON.stringify({ source_batch_id: 'batch-1', covered_item_ids: [], entries }, null, 2));
}

/** Plays the reviewer: answers each question in turn and records every question asked. */
function scripted(answers) {
  const asked = [];
  const ask = async (question) => {
    asked.push(question);
    if (!answers.length) throw new Error(`no scripted answer left for: ${question}`);
    return answers.shift();
  };
  return { ask, asked };
}

const silent = { print: () => {}, stream: { isTTY: false, columns: 100 } };

test('published_log.json only ever grows: earlier text is kept byte for byte', () => {
  const files = tempFiles();
  appendToPublishedLog(files.publishedLog, { entry_id: 'one', note: 'first' });
  const before = fs.readFileSync(files.publishedLog, 'utf8');
  appendToPublishedLog(files.publishedLog, { entry_id: 'two', note: 'second' });
  const after = fs.readFileSync(files.publishedLog, 'utf8');
  assert.ok(after.startsWith(before.slice(0, before.lastIndexOf(']')).trimEnd()));
  assert.deepEqual(JSON.parse(after).map((e) => e.entry_id), ['one', 'two']);
  assert.throws(() => appendToPublishedLog(files.publishedLog, { entry_id: 'two' }), /already in published_log\.json/);
});

test('an unreadable published log is never overwritten', async () => {
  const files = tempFiles();
  writeDrafts(files, { crime: entry('crime') });
  fs.writeFileSync(files.publishedLog, '{"oops": true}');
  await assert.rejects(run({ files, ask: async () => 'a', ...silent }), /must contain a JSON list/);
  assert.equal(fs.readFileSync(files.publishedLog, 'utf8'), '{"oops": true}');
});

test('each entry waits for an explicit decision; only approved and edited entries are published', async () => {
  const files = tempFiles();
  writeDrafts(files, {
    politicians: entry('politicians'),
    crime: entry('crime'),
    education: entry('education'),
    relief: entry('relief', { inference_paragraph: undefined, setup_line: 'And now, a breather.' }),
  });
  const reviewer = scripted([
    '', 'yes please', 'a', // politicians: blank and unclear answers are asked again, never taken as approval
    'e', '1', 'Put together, these two reports suggest a rough week. Side by side, they point to a city on edge.', 'd', 'a', // crime: edited, then approved
    's', // education: skipped
    'e', '3', 'Nobody at City Hall cares', 'n', 'd', 'a', // relief: a made-up quote is caught and declined; approved as drafted
  ]);
  const result = await run({ files, ask: reviewer.ask, ...silent, reviewer: 'tester', now: () => '2026-09-27T12:00:00.000Z' });

  assert.deepEqual(result.decisions, { politicians: 'approved', crime: 'edited', education: 'skipped', relief: 'approved' });
  assert.equal(reviewer.asked.filter((q) => q.startsWith('Politicians:')).length, 3);

  const log = JSON.parse(fs.readFileSync(files.publishedLog, 'utf8'));
  assert.deepEqual(log.map((e) => [e.category, e.review.decision]), [['politicians', 'approved'], ['crime', 'edited'], ['relief', 'approved']]);
  const crime = log.find((e) => e.category === 'crime');
  assert.match(crime.inference_paragraph, /rough week/);
  assert.equal(crime.review.changes[0].field, 'inference_paragraph');
  const relief = log.find((e) => e.category === 'relief');
  assert.equal(relief.setup_line, 'And now, a breather.');
  assert.equal(relief.highlights[1].quote, 'Nobody at City Hall will explain why');
  assert.ok(log.every((e) => e.highlights.every((h) => h.link && !('post_text' in h))));

  const drafts = JSON.parse(fs.readFileSync(files.drafts, 'utf8'));
  assert.equal(drafts.entries.education.review.decision, 'skipped');
  assert.equal(drafts.entries.crime.review.reviewer, 'tester');
});

test('stopping part way keeps what was decided, and the next session picks up the rest', async () => {
  const files = tempFiles();
  writeDrafts(files, { crime: entry('crime'), relief: entry('relief') });
  const first = await run({ files, ask: scripted(['a', 'q']).ask, ...silent });
  assert.equal(first.stopped, true);
  assert.deepEqual(first.decisions, { crime: 'approved' });

  const second = scripted(['a']);
  await run({ files, ask: second.ask, ...silent });
  assert.ok(second.asked.every((q) => !q.startsWith('Crime:')), 'the approved entry is not offered again');
  assert.deepEqual(JSON.parse(fs.readFileSync(files.publishedLog, 'utf8')).map((e) => e.category), ['crime', 'relief']);
});

test('an entry found in the log but not marked (a session that crashed) is not published twice', async () => {
  const files = tempFiles();
  writeDrafts(files, { crime: entry('crime') });
  appendToPublishedLog(files.publishedLog, { entry_id: 'batch-1:crime', category: 'crime', published_at: 'earlier', review: { decision: 'approved' } });
  const reviewer = scripted([]);
  await run({ files, ask: reviewer.ask, ...silent });
  assert.equal(reviewer.asked.length, 0);
  assert.equal(JSON.parse(fs.readFileSync(files.drafts, 'utf8')).entries.crime.review.decision, 'approved');
  assert.equal(JSON.parse(fs.readFileSync(files.publishedLog, 'utf8')).length, 1);
});

test('flagged entries need a second confirmation before approval', async () => {
  const files = tempFiles();
  writeDrafts(files, { crime: entry('crime', { review_flags: ['The opening text was filled in automatically.'] }) });
  const reviewer = scripted(['a', 'n', 's']);
  const result = await run({ files, ask: reviewer.ask, ...silent });
  assert.deepEqual(result.decisions, { crime: 'skipped' });
  assert.ok(!fs.existsSync(files.publishedLog));
});

test('the command line refuses to run without a person at a terminal', () => {
  const files = tempFiles();
  writeDrafts(files, { crime: entry('crime') });
  const result = spawnSync(process.execPath, [path.join(__dirname, '..', 'publish_review.js')], {
    input: 'a\na\n',
    env: { ...process.env, MD_WATCH_DIR: files.dir },
    encoding: 'utf8',
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /interactive terminal/);
  assert.ok(!fs.existsSync(files.publishedLog));
});
