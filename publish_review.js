#!/usr/bin/env node
'use strict';

/**
 * MD Watch, step 3 of 3: publish_review.js
 *
 * The human checkpoint. Shows each draft entry in draft_entries.json, one
 * category at a time, and asks the person at the keyboard to approve, edit or
 * skip it. Only approved entries (edited ones included) are appended to
 * published_log.json, the MD Watch page's permanent store of entries; entries
 * already in it are never changed or removed.
 *
 * This is the only script that writes published_log.json. It refuses to run
 * without an interactive terminal, has no auto-approve option, and never treats
 * a blank or unexpected answer as approval.
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline');
const { PATHS, readJsonFile, writeFileAtomic, writeJsonAtomic, withLock } = require('./lib/common');
const { COMMENTARY_LINE, categoryLabel, introField, introProblems, quoteAppearsIn, quoteHeadline, renderMarkdown } = require('./lib/entries');

/** Thrown when the reviewer stops the session (q, Ctrl+C or Ctrl+D). */
class StopReview extends Error {}

// ---------------------------------------------------------------------------
// published_log.json

/** Reads the published log, which must be a JSON list. Returns [] if the file does not exist yet. */
function readPublishedLog(file) {
  const log = readJsonFile(file);
  if (log === null) return [];
  if (!Array.isArray(log)) throw new Error(`${path.basename(file)} must contain a JSON list of entries`);
  return log;
}

/**
 * Adds one entry to the end of published_log.json. The file's existing text is
 * kept byte for byte: the new entry is inserted before the closing bracket, the
 * result is checked, and it replaces the file in a single atomic step. If the
 * file cannot be read as a list, nothing is written.
 */
function appendToPublishedLog(file, record) {
  const before = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : '';
  const existing = before.trim() ? readPublishedLog(file) : [];
  if (existing.some((entry) => entry.entry_id === record.entry_id)) {
    throw new Error(`${record.entry_id} is already in ${path.basename(file)}`);
  }
  const entryText = JSON.stringify(record, null, 2).replace(/^/gm, '  ');
  const kept = existing.length ? before.slice(0, before.lastIndexOf(']')).trimEnd() : '[';
  const after = existing.length ? `${kept},\n${entryText}\n]\n` : `[\n${entryText}\n]\n`;
  const check = JSON.parse(after);
  if (!after.startsWith(kept) || check.length !== existing.length + 1) {
    throw new Error(`refusing to write ${path.basename(file)}: the result would not keep every earlier entry`);
  }
  writeFileAtomic(file, after);
  return check.length;
}

function publishedRecord(entry, decision, changes, reviewer, when) {
  const field = introField(entry);
  return {
    entry_id: entry.draft_id,
    category: entry.category,
    published_at: when,
    [field]: entry[field],
    highlights: entry.highlights.map(({ post_text, link_check, ...highlight }) => highlight),
    sources: entry.sources.map(({ link_check, ...source }) => source),
    markdown: renderMarkdown(entry),
    review: { decision, reviewer, reviewed_at: when, ...(changes.length ? { changes } : {}) },
  };
}

// ---------------------------------------------------------------------------
// Terminal output

function makeUi(stream, print) {
  const color = Boolean(stream.isTTY) && !process.env.NO_COLOR;
  const style = (open, close) => (text) => (color ? `\x1b[${open}m${text}\x1b[${close}m` : String(text));
  const width = Math.max(50, Math.min(stream.columns || 80, 100));
  return {
    print,
    width,
    bold: style(1, 22),
    dim: style(2, 22),
    yellow: style(33, 39),
    green: style(32, 39),
    rule: (char) => char.repeat(width),
  };
}

function wrap(text, width, indent = '') {
  const lines = [];
  let line = '';
  for (const word of String(text ?? '').split(/\s+/).filter(Boolean)) {
    if (line && indent.length + line.length + 1 + word.length > width) {
      lines.push(indent + line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) lines.push(indent + line);
  return lines.join('\n');
}

function short(text, max = 60) {
  const value = String(text ?? '').replace(/\s+/g, ' ').trim();
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}

function showEntry(entry, position, total, alreadyPublished, ui) {
  const { print, bold, dim, yellow, rule, width } = ui;
  const field = introField(entry);
  print('');
  print(rule('='));
  print(`${bold(categoryLabel(entry.category).toUpperCase())}  ${dim(`entry ${position} of ${total}, ${entry.item_count} item(s), ${entry.highlights.length} highlight(s)`)}`);
  print(rule('='));
  print(bold(field === 'setup_line' ? 'Setup line' : 'Intro'));
  print(wrap(entry[field], width, '  '));
  print('');
  print(bold('Highlights'));
  if (!entry.highlights.length) print('  (none)');
  entry.highlights.forEach((h, i) => {
    print(wrap(bold(h.headline), width + 10, `  ${i + 1}. `).replace(/\n {5}/g, '\n     '));
    print(wrap(h.context_line, width, '     '));
    print(`     ${h.link}`);
    for (const related of h.related_links || []) print(`     Related: ${related}`);
    print(dim(`     ${h.source_name} (${h.source_type}), link ${h.link_check}`));
    print('');
  });
  print(bold(`Everything this entry covers (${entry.sources.length})`));
  for (const source of entry.sources) {
    print(`  - ${short(source.title, width - 6)} ${dim(`(${source.source_name})`)}`);
    print(dim(`    ${source.link}`));
  }
  if (entry.left_out?.length) {
    print('');
    print(bold(`Left out (${entry.left_out.length})`));
    for (const item of entry.left_out) print(dim(`  - ${short(item.title, width - 30)}: ${item.reason}`));
  }
  const warnings = [...(entry.review_flags || [])];
  const repeats = entry.sources.filter((source) => alreadyPublished.has(source.item_id));
  if (repeats.length) warnings.push(`${repeats.length} of these items already appear in published entries.`);
  if (warnings.length) {
    print('');
    print(yellow(bold('Check before approving')));
    for (const warning of warnings) print(yellow(wrap(`! ${warning}`, width, '  ')));
  }
  print('');
}

// ---------------------------------------------------------------------------
// Prompts

async function choose(ask, question, answers) {
  for (;;) {
    const answer = String(await ask(question)).trim().toLowerCase();
    for (const [choice, words] of Object.entries(answers)) if (words.includes(answer)) return choice;
  }
}

function confirm(ask, question) {
  return choose(ask, question, { yes: ['y', 'yes'], no: ['n', 'no'] }).then((choice) => choice === 'yes');
}

async function askForText(ask, ui, label, current) {
  ui.print(ui.dim(`Current ${label}:`));
  ui.print(wrap(current || '(empty)', ui.width, '  '));
  const answer = String(await ask(`New ${label} (press Enter to keep the current one): `)).replace(/\s+/g, ' ').trim();
  return answer || null;
}

/** Lets the reviewer change the entry's text. Returns the list of changes made. */
async function editEntry(entry, ask, ui) {
  const changes = [];
  const record = (field, from, to) => changes.push({ field, from, to });
  for (;;) {
    const field = introField(entry);
    const fieldLabel = field === 'setup_line' ? 'setup line' : 'intro';
    const options = [
      {
        label: `${fieldLabel.charAt(0).toUpperCase()}${fieldLabel.slice(1)}: ${short(entry[field])}`,
        run: async () => {
          const text = await askForText(ask, ui, fieldLabel, entry[field]);
          if (!text) return;
          const problems = introProblems(field, text);
          if (problems.length) {
            ui.print(ui.yellow(`Note: ${problems.join('; ')}.`));
            if (!(await confirm(ask, 'Use it anyway? [y/n] '))) return;
          }
          record(field, entry[field], text);
          entry[field] = text;
        },
      },
    ];
    entry.highlights.forEach((h, i) => {
      const n = i + 1;
      if (h.format === 'quote') {
        options.push({
          label: `Highlight ${n} quote: "${short(h.quote, 50)}"`,
          run: async () => {
            const text = await askForText(ask, ui, 'quote', h.quote);
            if (!text) return;
            const quote = text.replace(/^["'“”\s]+|["'“”\s]+$/g, '');
            if (h.post_text && !quoteAppearsIn(quote, h.post_text)) {
              ui.print(ui.yellow('That wording does not appear in the post. Quote highlights must be direct or near-direct quotes.'));
              if (!(await confirm(ask, 'Use it anyway? [y/n] '))) return;
            }
            record(`highlights[${i}].quote`, h.quote, quote);
            h.quote = quote;
            h.headline = quoteHeadline(quote, h.handle, h.source_name);
          },
        });
        options.push({
          label: `Highlight ${n} attribution: ${h.handle || `${h.source_name} (no handle)`}`,
          run: async () => {
            const text = await askForText(ask, ui, 'handle', h.handle);
            if (!text) return;
            const handle = text.startsWith('@') ? text : `@${text}`;
            record(`highlights[${i}].handle`, h.handle, handle);
            h.handle = handle;
            h.headline = quoteHeadline(h.quote, handle, h.source_name);
          },
        });
      } else {
        options.push({
          label: `Highlight ${n} headline: ${short(h.headline, 50)}`,
          run: async () => {
            const text = await askForText(ask, ui, 'headline', h.headline);
            if (!text) return;
            record(`highlights[${i}].headline`, h.headline, text);
            h.headline = text;
          },
        });
        options.push({
          label: `Highlight ${n} context line: ${short(h.context_line, 50)}`,
          run: async () => {
            const text = await askForText(ask, ui, 'context line', h.context_line);
            if (!text) return;
            if (!text.toLowerCase().includes(h.source_name.toLowerCase())) {
              ui.print(ui.yellow(`Note: the context line should name who reported or posted it (${h.source_name}).`));
              if (!(await confirm(ask, 'Use it anyway? [y/n] '))) return;
            }
            record(`highlights[${i}].context_line`, h.context_line, text);
            h.context_line = text;
          },
        });
      }
    });
    if (entry.highlights.length > 1) {
      options.push({
        label: 'Remove a highlight',
        run: async () => {
          const answer = String(await ask(`Remove which highlight? [1-${entry.highlights.length}, Enter to cancel] `)).trim();
          const index = Number(answer) - 1;
          if (!answer || !entry.highlights[index]) return;
          const [removed] = entry.highlights.splice(index, 1);
          record('highlights', removed.headline, null);
        },
      });
    }

    ui.print('');
    ui.print(ui.bold('Edit'));
    options.forEach((option, i) => ui.print(`  ${i + 1}) ${option.label}`));
    ui.print('  d) Done editing');
    ui.print(ui.dim('  Links come from the original posts and cannot be edited; remove the highlight instead.'));
    const answer = String(await ask('> ')).trim().toLowerCase();
    if (answer === 'd' || answer === 'done') break;
    const option = options[Number(answer) - 1];
    if (option) await option.run();
    else ui.print('Type a number from the list, or d when you are done.');
  }
  if (changes.length) entry.markdown = renderMarkdown(entry);
  return changes;
}

// ---------------------------------------------------------------------------
// Review session

function reviewerName() {
  try {
    return os.userInfo().username;
  } catch {
    return 'unknown';
  }
}

async function run(options) {
  const files = { ...PATHS, ...options.files };
  const { ask } = options;
  const ui = makeUi(options.stream || process.stdout, options.print || ((line) => console.log(line)));
  const now = options.now || (() => new Date().toISOString());
  const reviewer = options.reviewer || reviewerName();

  const drafts = readJsonFile(files.drafts);
  if (!drafts) {
    ui.print(`No ${path.basename(files.drafts)} to review. Run write_entries.js first.`);
    return { decisions: {} };
  }
  if (!drafts.entries || typeof drafts.entries !== 'object') throw new Error(`${path.basename(files.drafts)} is not in the expected format`);
  let published = readPublishedLog(files.publishedLog); // stop here, before any question, if the log is unreadable

  // An entry already in the log was approved in a session that ended before it
  // could be marked; record that instead of offering it again.
  const saveDrafts = () => writeJsonAtomic(files.drafts, drafts);
  for (const entry of Object.values(drafts.entries)) {
    const match = published.find((record) => record.entry_id === entry.draft_id);
    if (!entry.review && match) {
      entry.review = { decision: match.review?.decision || 'approved', reviewed_at: match.published_at, reviewer: match.review?.reviewer };
      saveDrafts();
    }
  }

  const all = Object.entries(drafts.entries);
  const toReview = all.filter(([, entry]) => !entry.review);
  const earlier = all.filter(([, entry]) => entry.review);
  if (earlier.length) {
    ui.print(ui.dim(`Already reviewed: ${earlier.map(([category, entry]) => `${categoryLabel(category)} (${entry.review.decision})`).join(', ')}`));
  }
  if (!toReview.length) {
    ui.print('Nothing waiting for review.');
    return { decisions: {} };
  }
  ui.print(`${toReview.length} draft entr${toReview.length === 1 ? 'y' : 'ies'} to review. Nothing is published unless you approve it.`);

  const decisions = {};
  let stopped = false;
  try {
    for (const [index, [category, entry]] of toReview.entries()) {
      const alreadyPublished = new Set(published.flatMap((record) => (record.sources || []).map((source) => source.item_id)));
      showEntry(entry, index + 1, toReview.length, alreadyPublished, ui);
      const changes = [];
      for (;;) {
        const choice = await choose(ask, `${categoryLabel(category)}: [a]pprove, [e]dit or [s]kip? (q to stop for now) `, {
          approve: ['a', 'approve'],
          edit: ['e', 'edit'],
          skip: ['s', 'skip'],
          stop: ['q', 'quit'],
        });
        if (choice === 'stop') throw new StopReview();
        if (choice === 'edit') {
          changes.push(...(await editEntry(entry, ask, ui)));
          showEntry(entry, index + 1, toReview.length, alreadyPublished, ui);
          continue;
        }
        if (choice === 'approve') {
          if (!entry.highlights.length) {
            ui.print(ui.yellow('This entry has no highlights, and every entry needs at least one linked highlight. Edit it or skip it.'));
            continue;
          }
          if (entry.review_flags?.length && !(await confirm(ask, `This entry has ${entry.review_flags.length} flag(s) listed above. Approve it anyway? [y/n] `))) continue;
          const decision = changes.length ? 'edited' : 'approved';
          const when = now();
          const total = appendToPublishedLog(files.publishedLog, publishedRecord(entry, decision, changes, reviewer, when));
          published = readPublishedLog(files.publishedLog);
          entry.review = { decision, reviewed_at: when, reviewer };
          saveDrafts();
          decisions[category] = decision;
          ui.print(ui.green(`${decision === 'edited' ? 'Edited and approved' : 'Approved'}: added to ${path.basename(files.publishedLog)} (${total} entries).`));
          break;
        }
        entry.review = { decision: 'skipped', reviewed_at: now(), reviewer };
        saveDrafts();
        decisions[category] = 'skipped';
        ui.print('Skipped: not published.');
        break;
      }
    }
  } catch (err) {
    if (!(err instanceof StopReview)) throw err;
    stopped = true;
  }

  printSummary(toReview.map(([category]) => category), decisions, stopped, files, ui);
  return { decisions, stopped };
}

function printSummary(categories, decisions, stopped, files, ui) {
  const { print, bold } = ui;
  const counts = (category, decision) => (decisions[category] === decision ? 1 : 0);
  const rows = categories.map((category) => [
    categoryLabel(category),
    counts(category, 'approved'),
    counts(category, 'edited'),
    counts(category, 'skipped'),
    decisions[category] ? '' : 'not reviewed yet',
  ]);
  const total = (col) => rows.reduce((sum, row) => sum + row[col], 0);
  rows.push(['Total', total(1), total(2), total(3), '']);
  const header = ['Category', 'Approved', 'Edited', 'Skipped', ''];
  const widths = header.map((h, col) => Math.max(h.length, ...rows.map((row) => String(row[col]).length)));
  const line = (row) => row.map((cell, col) => (col >= 1 && col <= 3 ? String(cell).padStart(widths[col]) : String(cell).padEnd(widths[col]))).join('  ').trimEnd();

  print('');
  print(bold(stopped ? 'Review stopped. Summary so far' : 'Review summary'));
  print(line(header));
  rows.forEach((row, i) => {
    if (i === rows.length - 1) print(widths.slice(0, 4).map((w) => '-'.repeat(w)).join('  '));
    print(line(row));
  });
  print('Edited = changed during review, then approved. Approved and edited entries were appended to');
  print(`${path.basename(files.publishedLog)}; skipped entries were not published.`);
  if (stopped) print('Run publish_review.js again to pick up where you left off.');
}

// ---------------------------------------------------------------------------

function terminalPrompter() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  let closed = false;
  rl.on('close', () => {
    closed = true;
  });
  rl.on('SIGINT', () => rl.close()); // Ctrl+C stops the review; nothing pending is approved
  const ask = (question) =>
    new Promise((resolve, reject) => {
      if (closed) return reject(new StopReview());
      const onClose = () => reject(new StopReview());
      rl.once('close', onClose);
      rl.question(question, (answer) => {
        rl.off('close', onClose);
        resolve(answer);
      });
    });
  return { ask, close: () => rl.close() };
}

async function main() {
  if (process.argv.length > 2) {
    console.error('publish_review.js takes no options: every entry is reviewed by hand.');
    process.exitCode = 2;
    return;
  }
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    console.error(
      'publish_review.js must be run by a person in an interactive terminal: every entry needs a human decision,\n' +
        'so it will not read answers from a pipe or file, write its output to one, or run as a scheduled job.',
    );
    process.exitCode = 1;
    return;
  }
  const prompter = terminalPrompter();
  try {
    // Shares a lock with write_entries.js: drafts are never rewritten mid-review.
    await withLock(PATHS.draftsLock, 'publish_review.js', () => run({ ask: prompter.ask }));
  } catch (err) {
    console.error(`\npublish_review.js stopped: ${err.message}\nEntries approved before this point are saved; nothing else was published.`);
    process.exitCode = 1;
  } finally {
    prompter.close();
  }
}

if (require.main === module) main();

module.exports = { run, appendToPublishedLog, readPublishedLog, COMMENTARY_LINE };
