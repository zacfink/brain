# Brain file formats

The app (`app/server.py`) parses these. Claude writes them. Keep to the shapes exactly;
free markdown is fine inside bodies. Dates are absolute `YYYY-MM-DD`.
All names below are fictional examples.

## `me.md`
```
---
name: Sam Rivera
tagline: One line, in your own voice
updated: 2026-09-14
---
# About Sam
## Snapshot        — who you are right now (bullets)
## Goals           — this year / this term. Mark guesses "(draft — confirm)"
## How I work      — preferences, routines, tools, how to reach you
## Interests       — topics, things you want to learn/build
## Skills & tools
## Background      — dated bullets, newest first
```

## `people/<slug>.md`
```
---
name: Priya Shah
relation: Northside Coffee — club sponsorship contact   # one line
circle: work                                            # any word; family | friends | work | school | other …
last_contact: 2026-09-04                                # blank if unknown
follow_up: Waiting on her to pick a meeting time        # one line, blank if none
links: [mailto:priya@example.com]
---
# Priya Shah
**TL;DR:** One sentence.
## Who they are
## History          — dated bullets, newest first
## Open loops       — "- [ ] ..." items
```

## `nudges.md` — reminders for you
Claude adds one only when it clearly helps. Status `no` is permanent: never re-add that nudge.
```
# Nudges

## N-001 · Reply to Priya about the sponsorship
- status: open            # open | done | snoozed | no
- due: 2026-09-14         # optional
- snooze_until:           # set by the app
- done_on:                # set by the app
- why: You said you'd send her two meeting times by Friday.
- project: design-club
- source: sessions/2026-09-04-sponsor-outreach.md
- created: 2026-09-14
```

## `claude/habits.md` — how Claude adapts to you
`on` habits are followed every session. `proposed` ones wait for you to flip them on in the app.
```
# Claude's habits

## H-001 · Lead with the answer, keep it short
- status: on              # on | off | proposed
- why: You asked for shorter responses.
- since: 2026-09-04
- source: conversation, 2026-09-04
```

## `now.md` — the cover story
Claude rewrites after real work. Headline is punchy, magazine-style, true. `*word*` renders italic.
```
---
headline: The site is live. *Now* the club has to show up.
dek: One or two sentences of real detail.
project: design-club        # slug the cover's buttons reopen
updated: 2026-09-14
---
## Upcoming
- 2026-09-17 18:00 · Design club workshop 1 · Room 101
- 2026-09-21 · Sponsorship deck due · Send to Priya
```

## `ideas.md`
```
# Ideas
- 2026-09-14 · Idea text — optional note (project: slug)
```

## `inbox.md` — quick captures from the app
The app appends; Claude files each line into the right note at the start of the next session and deletes it.
```
# Inbox
- 2026-09-14 19:02 · idea · text
```
Kinds: `note`, `idea`, `todo`, `person`.

## `projects/<slug>.md` and `sessions/YYYY-MM-DD-<slug>.md`
Project pages: frontmatter `name, status (active|paused|done|abandoned), updated, paths: [...], links: [...], summary`,
then `**TL;DR:**` and sections. Session notes: see `session-template.md`. A session's `session:` id (first 8 chars
of the Claude Code session id) powers the app's "resume chat" button.
