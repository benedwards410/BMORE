'use strict';

// Shared by the three MD Watch scripts: where the pipeline's files live and how
// they are read and written.

const fs = require('node:fs');
const path = require('node:path');

// Data files live next to the scripts unless MD_WATCH_DIR points elsewhere.
const DATA_DIR = process.env.MD_WATCH_DIR
  ? path.resolve(process.env.MD_WATCH_DIR)
  : path.resolve(__dirname, '..');

const PATHS = {
  config: path.join(DATA_DIR, 'feeds.json'),
  seenDb: path.join(DATA_DIR, 'seen_items.db'),
  pending: path.join(DATA_DIR, 'pending_items.json'),
  drafts: path.join(DATA_DIR, 'draft_entries.json'),
  publishedLog: path.join(DATA_DIR, 'published_log.json'),
  env: path.join(DATA_DIR, '.env'),
  fetchLock: path.join(DATA_DIR, '.fetch.lock'),
  draftsLock: path.join(DATA_DIR, '.drafts.lock'),
};

// A lock older than this is treated as left behind by a run that died.
const STALE_LOCK_MS = 6 * 60 * 60 * 1000;

// Feeds of this type skip keyword matching and are filed under a category of the same name.
const RELIEF = 'relief';

/** Parses a JSON file. Returns null if the file does not exist; throws if it is not valid JSON. */
function readJsonFile(file) {
  let text;
  try {
    text = fs.readFileSync(file, 'utf8');
  } catch (err) {
    if (err.code === 'ENOENT') return null;
    throw err;
  }
  try {
    return JSON.parse(text);
  } catch (err) {
    throw new Error(`${path.basename(file)} is not valid JSON (${err.message})`);
  }
}

/**
 * Replaces a file's contents without ever leaving it half-written: the text goes
 * to a temporary file first, which is flushed to disk and then renamed over the
 * target in one step.
 */
function writeFileAtomic(file, text) {
  const tmp = `${file}.${process.pid}.tmp`;
  try {
    const fd = fs.openSync(tmp, 'w');
    try {
      fs.writeSync(fd, text);
      fs.fsyncSync(fd);
    } finally {
      fs.closeSync(fd);
    }
    fs.renameSync(tmp, file);
  } catch (err) {
    fs.rmSync(tmp, { force: true });
    throw err;
  }
}

function writeJsonAtomic(file, data) {
  writeFileAtomic(file, `${JSON.stringify(data, null, 2)}\n`);
}

function isHttpUrl(value) {
  if (typeof value !== 'string') return false;
  try {
    const { protocol } = new URL(value);
    return protocol === 'http:' || protocol === 'https:';
  } catch {
    return false;
  }
}

/** Like Promise.all(values.map(fn)), but with at most `limit` calls in flight. Keeps the order of `values`. */
async function mapLimit(values, limit, fn) {
  const results = new Array(values.length);
  let next = 0;
  const worker = async () => {
    while (next < values.length) {
      const i = next++;
      results[i] = await fn(values[i]);
    }
  };
  await Promise.all(Array.from({ length: Math.min(limit, values.length) }, worker));
  return results;
}

/**
 * Loads API keys from the .env file next to the scripts, if there is one, so
 * scheduled runs (cron, Task Scheduler) get them without any shell setup.
 * Variables already set in the environment win over the file.
 */
function loadEnvFile(file = PATHS.env) {
  try {
    process.loadEnvFile(file);
  } catch (err) {
    if (err.code !== 'ENOENT') throw new Error(`could not read ${path.basename(file)}: ${err.message}`);
  }
}

function processIsRunning(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return err.code === 'EPERM';
  }
}

/**
 * Runs fn while holding a lock file, so two runs that write the same files never
 * overlap (say, a scheduled fetch that fires while the previous one is still
 * going). A lock whose process has exited, or that is hours old, is taken over.
 */
async function withLock(file, owner, fn) {
  const mine = JSON.stringify({ pid: process.pid, owner, started_at: new Date().toISOString() });
  for (let attempt = 0; ; attempt++) {
    try {
      fs.writeFileSync(file, mine, { flag: 'wx' });
      break;
    } catch (err) {
      if (err.code !== 'EEXIST' || attempt > 0) throw err;
      let holder = null;
      try {
        holder = JSON.parse(fs.readFileSync(file, 'utf8'));
      } catch {
        // unreadable lock: treat as stale
      }
      if (holder && processIsRunning(holder.pid) && Date.now() - Date.parse(holder.started_at) < STALE_LOCK_MS) {
        throw new Error(`${holder.owner} is already running (process ${holder.pid}, started ${holder.started_at}); try again when it finishes`);
      }
      fs.rmSync(file, { force: true });
    }
  }
  try {
    return await fn();
  } finally {
    try {
      if (fs.readFileSync(file, 'utf8') === mine) fs.rmSync(file, { force: true });
    } catch {
      // already gone
    }
  }
}

module.exports = {
  DATA_DIR,
  PATHS,
  RELIEF,
  readJsonFile,
  writeFileAtomic,
  writeJsonAtomic,
  isHttpUrl,
  mapLimit,
  loadEnvFile,
  withLock,
};
