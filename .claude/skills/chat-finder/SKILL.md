---
name: chat-finder
description: Find past Claude conversations by what was said in them, not just by title, then sort and filter the results. Use whenever the user types #Find or "find chat", asks to search, find, dig up, or list past chats or conversations, says things like "where did we talk about…", "which chat had…", "I discussed X with you before", or "find the chat where we made the…", or wants past chats sorted by date or filtered by topic, person, project, artifact, or time period, even if they never say "search". Not for searching the web, files, email, or documents.
---

# Chat finder

The search box in the Claude apps mostly matches titles, misses keywords, and can't sort by date. Claude's own past-chat tools search what was actually said and can list chats by date. This skill uses them thoroughly, then filters and sorts the results the way the user asks.

## Tools and limits

- **In the Claude apps:** `conversation_search` searches past chats by content. `recent_chats` lists chats by time, newest or oldest first, and takes before and after dates. Both exist only when "Search and reference chats" is turned on in Settings. If they're missing, say so in one line and tell the user where to turn it on. Don't pretend to search.
- **Scope:** inside a project, these tools only see that project's chats. Outside a project, they only see chats that aren't in any project. Always say which scope you searched. If the chat the user wants might be in the other scope, tell them to run the search there.
- **In Claude Code:** past sessions are transcript files (locally under `~/.claude/projects/<project>/`); search them with grep. In cloud sessions, use the session tools to list sessions and read their events, if they're available.
- **Never invent anything.** Report only chats, titles, dates, and links that a tool actually returned.

## 1. Read the ask

Pull out four things: **what** (the topic words), **when** (a date range, if any), **sort**, and **filters**. If something essential is unclear and a wrong guess would waste a whole search round, ask one quick round of 2–3 tappable questions. Otherwise, search right away. Most finds don't need questions.

## 2. Search wide

Built-in search misses mostly because people remember different words than they used. So:

- **Build 3–6 query variants:** the user's exact words; synonyms; abbreviations and full forms; singular and plural; names of the people, companies, or projects involved; likely misspellings; the kind of thing made ("deck", "plan", "draft", "spreadsheet").
- **Keep each query short and distinctive,** 1–3 words. Generic words like "help" or "plan" on their own match everything.
- **Run each content search** with the largest result count the tool allows.
- **For a date range or a date sort,** also walk `recent_chats` across the window: newest first, bounded by after and before, paging back by using the oldest date in each batch as the next "before". Check each chat's title and snippet for the target. Stop after about five pages (roughly 100 chats) unless the user asks for more, and say where you stopped.
- **If results are thin,** try a second round of variants before reporting nothing.

## 3. Merge

Remove duplicates by chat link. For each chat, keep its title, link, last-active date, which queries hit it, and a one-line gist based on what you saw.

## 4. Sort and filter

**Sorts**

| Sort | How |
|---|---|
| Last active, newest first (default) | From the tool's timestamp. Reliable. |
| Oldest first | Same timestamp, reversed. |
| Date created | Only if the tools return a creation date. They usually return last activity only; if so, say that once and sort by last active. |
| Best match | Chats hit by the most query variants, or by the most distinctive terms, first. |
| Artifacts first | Chats where something was made come first. Inferred (see below). |

**Filters that use tool data** (reliable)
- Date range: exact dates or plain phrases like "last week", "in September", "since August".
- Project scope.
- Words in the title.

**Filters inferred from content** (best effort; mark these results with ~)
- Something was made (an artifact, doc, deck, code, spreadsheet, chart, page), and which kind.
- The user uploaded files or images.
- A person, company, or place is mentioned.
- Money amounts, numbers, or dates appear.
- A decision was made, action items were listed, or loose ends were left open.
- **Said by me:** match only the user's own messages. Useful when someone remembers saying something rather than reading it.
- Exact phrase versus loose match.
- Exclude terms ("not the invoice one").
- The chat used a skill: started with #GO, has parked items, or has a "title chat" summary.
- Long chats versus short ones.

Inferred filters depend on the snippets the tools return, so a chat can slip through when its snippet doesn't show the evidence. When an inferred filter shaped the list, say so.

## 5. Report

Lead with the bottom line: "Found 6 chats. The one you likely want is #1."

| # | Last active | Title | What it covered | Why it matched | Link |
|---|---|---|---|---|---|

- Dates in full ("Oct 3, 2026"), never "3 days ago", so the list still makes sense later.
- "What it covered" is one line, in the user's terms.
- "Why it matched" names the terms that hit, plus ~ markers for inferred filters.

Then one coverage line: the queries you ran, the scope you searched, the date window you walked, and where you stopped. Say the list may be incomplete only when you actually stopped early or the scope was limited.

Then offer next steps: recap one of the chats, narrow or widen the search, re-sort, or run "title chat" in any chat whose title didn't match its content, since that mismatch is usually why it was hard to find.

**When nothing turns up:** say what you tried and which scope you searched, then suggest 2–3 concrete next tries (the other scope, different words, a wider date range). Don't pad the list with weak matches. If you show any, label them as weak.

## Example

User: "#Find the chat where we built the owners plan, newest first, only ones where we made a doc"

- Queries: `owners plan`, `2027 plan`, `owner plan one-page`, `FLOW lifecycle`, `annual plan owners`
- Scope: chats outside projects
- Filter: ~something made (doc)
- Sort: last active, newest first

> Found 3 chats; #1 is the one with the finished one-page plan.
>
> | # | Last active | Title | What it covered | Why it matched | Link |
> |---|---|---|---|---|---|
> | 1 | Oct 6, 2026 | Help me plan 2027 | One-page owners plan; FLOW reframed | owners plan, FLOW, ~doc | … |
> | 2 | Sep 28, 2026 | Owner goals | Early outline of owner targets | owners plan, ~doc | … |
> | 3 | Sep 12, 2026 | Q3 review | Q3 numbers, mentions 2027 plan | 2027 plan, ~doc | … |
>
> Searched 5 variants, chats outside projects. Want a recap of #1, or a better title for it? "Help me plan 2027" undersells it.
