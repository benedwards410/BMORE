'use strict';

// Shared by write_entries.js and publish_review.js: the rules a draft entry's
// text has to follow, and how an entry is rendered.

// The fixed context line under every quote-style highlight.
const COMMENTARY_LINE = 'Commentary. Please, fact check yourself.';

// An inference paragraph must say out loud that it is interpretation.
const INTERPRETIVE_FRAMING =
  /\b(put together|taken together|side by side|read together|together, (these|they)|(these|they) suggest|suggests?|points? to|pointing to|hints? at|seems? to|appears? to|looks? like|reads? like)\b/i;

// Abbreviations that end in a period without ending the sentence.
const ABBREVIATION = /\b(Gov|Lt|Sen|Del|Rep|Rev|Gen|Sgt|Mr|Mrs|Ms|Dr|St|Jr|Sr|Md|No|vs|U\.S|D\.C)\.$/i;

/** "cost_of_living" -> "Cost of Living" */
function categoryLabel(category) {
  return category
    .split('_')
    .map((word, i) => (i > 0 && ['of', 'and', 'the', 'in'].includes(word) ? word : word.charAt(0).toUpperCase() + word.slice(1)))
    .join(' ');
}

/** Which field holds an entry's opening text: relief has a setup line, the rest an inference paragraph. */
function introField(entry) {
  return 'setup_line' in entry ? 'setup_line' : 'inference_paragraph';
}

function sentences(text) {
  const out = [];
  for (const { segment } of new Intl.Segmenter('en', { granularity: 'sentence' }).segment(text)) {
    const sentence = segment.trim();
    if (!sentence) continue;
    if (out.length && ABBREVIATION.test(out[out.length - 1])) out[out.length - 1] += ` ${sentence}`;
    else out.push(sentence);
  }
  return out;
}

/** What is wrong with an entry's opening text, as a list of plain-language problems. */
function introProblems(field, text) {
  const value = (text || '').trim();
  if (!value) return ['it is empty'];
  const count = sentences(value).length;
  if (field === 'setup_line') {
    return count > 1 || value.includes('\n') ? ['the setup must be a single sentence on one line'] : [];
  }
  const problems = [];
  if (count < 2 || count > 4) problems.push(`the inference paragraph must be 2 to 4 sentences (it has ${count})`);
  if (!INTERPRETIVE_FRAMING.test(value)) {
    problems.push('the inference paragraph must be framed explicitly as interpretation, e.g. "Put together, these suggest..."');
  }
  return problems;
}

function comparable(text) {
  return (text || '')
    .normalize('NFKC')
    .replace(/[‘’ʼ]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/[‐-―]/g, '-')
    .replace(/\s+/g, ' ')
    .toLowerCase()
    .trim();
}

/**
 * True when every piece of the quote appears word for word, in order, in the
 * source text. Pieces are separated by an ellipsis, so a quote may be trimmed
 * ("near-direct"), but not reworded. Case, curly quotes and spacing are ignored.
 */
function quoteAppearsIn(quote, sourceText) {
  const source = comparable(sourceText);
  const pieces = comparable(quote)
    .split(/\s*(?:\.\.\.|…)\s*/)
    .map((piece) => piece.replace(/^[\s"'.,;:!?-]+|[\s"'.,;:!?-]+$/g, ''))
    .filter(Boolean);
  if (!pieces.length || pieces.join(' ').split(' ').length < 3) return false;
  let from = 0;
  for (const piece of pieces) {
    const at = source.indexOf(piece, from);
    if (at === -1) return false;
    from = at + piece.length;
  }
  return true;
}

/** A quote-style headline: "[quote]" —@handle (the source's name when no handle is known). */
function quoteHeadline(quote, handle, sourceName) {
  return `"${quote}" —${handle || sourceName}`;
}

/** The entry as Markdown, the way it would appear on the MD Watch page. */
function renderMarkdown(entry) {
  const lines = [`## ${categoryLabel(entry.category)}`, '', entry[introField(entry)], ''];
  for (const h of entry.highlights) {
    const block = [`**${h.headline}**`, h.context_line, `<${h.link}>`, ...(h.related_links || []).map((r) => `Related: <${r}>`)];
    lines.push(block.join('\\\n'), ''); // a trailing backslash is a Markdown line break
  }
  return lines.join('\n').trimEnd();
}

module.exports = {
  COMMENTARY_LINE,
  categoryLabel,
  introField,
  sentences,
  introProblems,
  quoteAppearsIn,
  quoteHeadline,
  renderMarkdown,
};
