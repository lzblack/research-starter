# Pilot measurement plan

The pilots use v0 on several real projects for several months, covering at least one solo and one
team project and both open and closed visibility (PRD section 18). They are compared descriptively:
a few pilots show whether the template works for their owners, not whether it would work for
others, and they do not establish a causal effect.

This plan defines how each measure is collected. Pilot details, such as the projects and people,
stay in the maintainer's private notes.

## Measures

| Measure | Definition | Collection |
|---|---|---|
| Setup success | `generate` and the local `accept` checks pass on the first attempt; a first attempt ends when the user or agent changes the answers file or the template | the project's first session journal entry and `docs/retro/` entries |
| Setup time | wall-clock time from the first setup question to the initial commit | recorded in the first journal entry |
| Handoff coverage | the share of work sessions that end with a handoff commit; sessions are counted from journal entries plus the commits that `session.py uncovered` reports at session start | journal entries and git history, counted at the end of the pilot |
| Problems caught by checks | failures and warnings from `build.py check` and the pre-commit hook that led to a change, by check ID; each is adjudicated as a real problem or a false positive | a `docs/retro/` entry for each adjudicated finding |
| Retro entries | the number of entries in `docs/retro/`, by `kind` | the files themselves |
| Manual migrations | whether each documented migration to a newer template version was followed without errors | a `docs/retro/` entry per migration |

## How the results are used

The pilots are few, so their results are descriptive and there are no numeric thresholds. They
follow PRD section 18: build what the pilots use, fix what hurts.

- Every failed setup and every friction that recurs becomes an issue in this repository and is
  fixed, together with a test or fixture where one applies.
- A configuration that no pilot exercised, such as team mode or open visibility, is reported as
  unverified. Its features are not removed for lack of use.
- When the pilots end, a review of the measures above decides what is core, what becomes a
  module, and what is removed. The review is recorded as a decision in `docs/decisions/`.
