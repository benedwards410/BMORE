'use strict';

// Stands in for the Anthropic client in tests. It answers write_entries.js's
// requests with well-formed drafts built from the items it was sent, and
// records every request so tests can inspect them.
//
//   misquoteFirst: section labels whose first reply paraphrases its quotes
//   refuse:        section labels that always come back as a refusal

function itemsFromPrompt(text) {
  const start = text.indexOf('Items:\n') + 'Items:\n'.length;
  const end = text.indexOf('\n\nA previous draft');
  return JSON.parse(text.slice(start, end === -1 ? undefined : end));
}

function fakeClaude({ misquoteFirst = [], refuse = [] } = {}) {
  const requests = [];
  const attempts = new Map();
  const create = async (params) => {
    requests.push(params);
    const prompt = params.messages[0].content;
    const section = /^Section: (.+)$/m.exec(prompt)[1];
    const attempt = (attempts.get(section) || 0) + 1;
    attempts.set(section, attempt);
    if (refuse.includes(section)) return { model: params.model, stop_reason: 'refusal', content: [] };

    const relief = section === 'Relief';
    const items = itemsFromPrompt(prompt);
    const highlights = items
      .filter((item) => item.can_highlight)
      .slice(0, 3)
      .map((item) => {
        // In relief, a first-person post reads as the creator's own framing.
        const format = relief ? (/\bI\b/.test(item.title) ? 'quote' : 'headline') : item.highlight_format;
        if (format === 'quote') {
          const words = item.title.split(' ').slice(0, 8).join(' ');
          const quote = misquoteFirst.includes(section) && attempt === 1 ? `${words}, allegedly` : words;
          return { item_id: item.id, format, headline: '', context_line: '', quote };
        }
        return {
          item_id: item.id,
          format,
          headline: `${item.title.toUpperCase()} — WHAT NOW?`,
          context_line: relief ? `Posted by ${item.handle || item.source}.` : `${item.source} reports the story.`,
          quote: '',
        };
      });
    const intro = relief
      ? 'And now, a breather: the animals are winning today.'
      : `Put together, these ${items.length} items suggest ${section.toLowerCase()} is heating up. Side by side, they point to the same pressure points.`;
    return {
      model: params.model,
      stop_reason: 'end_turn',
      content: [
        { type: 'thinking', thinking: '' },
        { type: 'text', text: JSON.stringify({ intro, highlights }) },
      ],
    };
  };
  return { requests, beta: { messages: { create } } };
}

module.exports = { fakeClaude };
