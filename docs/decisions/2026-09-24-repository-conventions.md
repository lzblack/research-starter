# Working conventions for this repository

Date: 2026-09-24

## Decision

- Session notes are one file per session in `journal/`. That folder is gitignored and stays on the
  maintainer's machine.
- A decision file is written only for a decision that changes scope, licensing, architecture or
  interfaces, data handling, or this repository's rules. Smaller changes are explained in commit
  messages.
- Decision files state the reasons that are suitable for a public record.
- Before committing docs, decisions, or issue text, check them for personal names, institutions,
  personal relationships between people, and pilot details.
- The public-content rule bans private identities and non-synthetic research examples. Required
  attribution, license notices, citation metadata, and names of public tools and projects are
  allowed. The scanner does not claim to find every real name.
- GitHub issues are the shared task list. Each milestone of an approved plan gets an issue labeled
  `milestone`, and unfinished work gets an issue at handoff. Deferred template features are listed
  only in the PRD's Later section until one is picked up. Project matters that are not template
  features are tracked as issues.

## Reason

This repository is public, and its session notes are personal working records, similar to an
agent's local notes. Fewer and larger decision files are easier to read and less likely to expose
unintended context. A literal ban on all names would conflict with license notices and attribution.
Keeping deferred features in a single list stops the PRD and the issue tracker from drifting apart
while one person maintains both.

## Alternatives considered

- Commit the journal and record every PRD change as its own decision.
- Keep the journal and decisions in a separate private repository.
- Keep no decision files and rely on the PRD and commit messages.
- Open a `later` issue for every deferred feature.

## Decided by

maintainer
