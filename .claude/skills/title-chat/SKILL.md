---
name: title-chat
description: Summarize the current chat and suggest 3–5 searchable titles for it. Use whenever the user's message is "title chat" (any capitalization, with or without a #), "#Title", or they ask to name, rename, retitle, or label this chat or conversation, or ask what this chat should be called. Works mid-task and in chats that jumped between topics. Not for titling documents, emails, slides, or other things being made in the chat; only the chat itself.
---

# Title chat

Claude names a chat from its first message, so a chat that wanders ends up with a title that only describes where it started. That makes it hard to find later. This skill reads the whole chat, summarizes it, and offers titles that describe all of it, in the words the user will actually search for.

There's a second benefit: the summary itself lands in the chat. Later content searches can hit its keywords, so running "title chat" at the end of a long chat makes that chat easier to find even if the user never renames it.

## Steps

1. **Read the whole chat**, start to finish, not just the latest messages. Note each distinct topic in the order it came up, plus anything concrete: names of people, companies, projects, places, files, artifacts made, decisions, numbers, dates.
2. **Write the summary** (format below).
3. **Write 3–5 title options.**
4. **Say how to apply it.**

## Output

**Summary** (as of today's date)
- One bullet per topic, in the order they came up: what it was about and where it landed (decided, drafted, open, parked, dropped).
- **Made:** artifacts, documents, files, or code created, by name. Leave this line out if nothing was made.
- **Open:** loose ends still waiting. Leave this line out if there are none.
- **Keywords:** 6–10 distinctive search terms: proper nouns, project names, unusual terms. Include both forms when the user used an abbreviation and its full form, since either one might be what they type into search later.

**Title options**, numbered, best first, marked (Recommended):
- Each under about 60 characters, because the sidebar cuts titles off. Put the most distinctive words first.
- Mix styles so the user can pick the one that fits how they look for things:
  - *Topic list:* `Owners plan 2027 · FLOW lifecycle · invoice fix`
  - *Outcome:* `2027 owners plan drafted; FLOW reframed`
  - *Main thread + extras:* `2027 owners plan (+ to-do list, invoice)`
  - *Keyword first:* `FLOW customer lifecycle – 2027 owners plan`
  - *Date first,* only when the chat is tied to a date or event: `Oct 2026 · board prep · owners plan`

Use the user's own words for things: their project names, their spelling, their abbreviations. Those are what they'll type into search, and a polished paraphrase won't match. Skip filler words like "Discussion of", "Help with", or "Chat about"; they take up space and never get searched. No emoji unless the user uses them.

## Topic jumps

If the chat covers more than about three unrelated topics, add one line after the titles naming the topic(s) that might be worth their own chat, and offer a short handoff note the user can paste into a new chat. It's a suggestion, not a push. Plenty of people work this way on purpose.

## Applying the title

Claude can't rename chats in the Claude apps, so say once, briefly, how to do it: click the chat title (at the top of the chat, or its menu in the sidebar), choose Rename, and paste.

If a tool that sets the chat or session title is available (for example in Claude Code cloud sessions), offer to apply the user's pick, and apply it only after they choose.

## Running it again

If "title chat" runs again later in the same chat, cover the whole chat again, not just the new part, and say in one line what changed since the last summary.

## Example

A chat started with "help me plan 2027 for the owners", then moved on to a six-item to-do list, an invoice dispute with a vendor named Arlo, and a reframing of FLOW as the full customer lifecycle.

**Summary** (as of Oct 10, 2026)
- 2027 owners plan: one-page draft built; targets left blank for the owners.
- To-do list: six items parked word for word; two done.
- Arlo invoice: disputed $4,200 line; reply drafted, not sent.
- FLOW: reframed as the whole customer lifecycle; folded into the plan.
- **Made:** 2027 owners plan (doc), Arlo reply (draft)
- **Open:** Arlo reply, plan targets
- **Keywords:** owners plan, 2027, FLOW, customer lifecycle, Arlo, invoice, dispute, to-do

**Title options**
1. `2027 owners plan · FLOW lifecycle · Arlo invoice` (Recommended)
2. `2027 owners plan drafted; FLOW reframed`
3. `Owners plan 2027 (+ to-dos, Arlo invoice)`
4. `FLOW customer lifecycle – 2027 owners plan`

The Arlo invoice could be its own chat. Want a handoff note to paste?

To rename: click the chat title → Rename → paste.
