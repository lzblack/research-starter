---
name: handoff
description: End-of-session write-back. Records a journal entry, any decisions, and issues for unfinished work, then commits with the session trailers and pushes. Use when the user ends a session, changes topic, an issue is done, or context is getting heavy.
---

# Handoff

Write what this session produced into the repository, so the next session (yours or anyone's)
can continue from the repository alone. Write everything in the repository language (AGENTS.md).

1. Get a session ID and journal path:
   `uv run python .agents/skills/handoff/session.py new --at <session start, e.g. 2026-01-15T09:30Z>`.
   Omit `--at` if you do not know when the session started.
2. Write the journal entry at that path:

   ```markdown
   ---
   session: <session ID>
   author: <the person's name as in project.yml>
   agent: <your tool and version>
   model: <your model, or unknown>
   ---

   ## Done
   ## Decisions
   ## Open
   ## Next
   ## AI use
   ```

   - Under Decisions, link each decision file, or write "None".
   - Under AI use, say in one to three sentences what you did in this session.
   - Record conclusions reached outside the repository (chat, email, meetings) as well.
3. For each decision that changes scope, data handling, methods, or interfaces:
   - get an ID with `uv run python .agents/skills/handoff/session.py decision-id <slug>`;
   - write `docs/decisions/<ID>.md` in the format below;
   - never edit an old decision; to change one, write a new file that lists it in `supersedes`.

   ```markdown
   ---
   id: <ID>
   date: <YYYY-MM-DD>
   decided_by:
     - <name>
   supersedes: []
   kind: decision
   ---

   ## Decision
   ## Reason
   ## Alternatives considered
   ```

4. Open an issue for each piece of unfinished work: `gh issue create`, after the user confirms
   the titles. If `gh` is not available, list the work under Open instead.
5. Commit with these two trailers:

   ```
   Session: <session ID>
   AI-Assisted: <your tool> (<your model>)
   ```

   Commit even when nothing else changed (`git commit --allow-empty`), for example when
   `journal/` is gitignored. The trailer is how the next session finds this handoff.
6. Push if a remote is configured. Report what you wrote and anything you could not do.
7. If something in the workflow got in the way this session, or worked well, offer to write a
   retro entry (`docs/retro/`, format in README.md).

Never edit sections listed as human-drafted in AGENTS.md, and never commit files from
`meetings/raw/` or `private/`.
