# Memory and accountability record formats

Date: 2026-09-24

## Decision

- Journal entries are named by the session's start time in UTC plus a random suffix. The handoff
  commit carries a `Session:` trailer, even when it has no other changes. At session start,
  recovery counts a commit as covered if it is a handoff commit or an ancestor of one. It reports
  the current user's commits that are not covered.
- Per-session AI-use records live in each journal entry and in an `AI-Assisted:` commit trailer.
  `docs/ai-use.md` is a summary that the consolidate skill refreshes from the committed trailers
  and any journal entries available locally.
- Workflow retro entries are one file each in `docs/retro/`, replacing the single file
  `docs/workflow-retro.md`. The PRD is updated accordingly.
- Decisions, retro entries, and claim audits use a date, a slug, and a random suffix in their file
  names. Records created by setup use a fixed suffix so that setup stays deterministic.
- `docs/status.md` is capped at 8000 bytes, enforced by check.

## Reason

The PRD requires that nothing shared is a single file appended to by every session. A per-session
AI-use record in a single file, or a shared retro file, would conflict between parallel branches.
Separate retro files also make retro entries easy to count, which the pilot measures need. UTC
start times keep names unique across time zones. A commit trailer lets recovery find handoffs
whether or not the journal is tracked. Checking all ancestors rather than only the first-parent
history keeps merged branches from appearing as missed handoffs.

## Alternatives considered

- Keep `docs/ai-use.md` and `docs/workflow-retro.md` as single files edited only by the lead during
  consolidation.
- Local time in journal names, or a journal entry that lists the commits it covers.

## Decided by

maintainer
