---
name: consolidate
description: Merge recent journal entries into docs/status.md and refresh docs/ai-use.md. Use when the lead asks to consolidate, or when status is out of date.
---

# Consolidate

1. Check who is running the session. Only the lead edits `docs/status.md`. The lead is the first
   person in `project.yml`.
   - If the user is not the lead, do the steps below as a proposal in the conversation. Do not
     edit the files.
2. Read `docs/status.md` and the journal entries written since the session it names as last
   consolidated.
3. Rewrite `docs/status.md` as the current state: goals, what is done, what is open, and the
   next steps.
   - Keep it under 8000 bytes; `uv run build.py check` enforces this.
   - End it with a line `Last consolidated: <newest session ID>`.
4. Refresh `docs/ai-use.md` with the headings `## Tools`, `## What AI assistance covered`,
   `## Human-drafted sections`, and `## Last refreshed`. Base it on the committed trailers
   (`git log --format='%(trailers:key=AI-Assisted,valueonly)'`) and the journal entries
   available here.
5. Run `uv run build.py check`, then commit with the `AI-Assisted:` trailer.
