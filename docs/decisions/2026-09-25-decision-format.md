# Decision file format in this repository

Date: 2026-09-25

## Decision

This repository keeps its decision format: `docs/decisions/YYYY-MM-DD-slug.md` with a `Date:` line
and the headings Decision, Reason, Alternatives considered, and Decided by. Generated projects use
the appendix A6.3 format, with a random suffix and YAML front matter. AGENTS.md states the
exception.

## Reason

One maintainer writes this repository's decisions, and there are few of them, so the file names
do not collide and nothing reads them by machine. The A6.3 format exists for parallel team
branches and for record checks, which this repository does not need. Rewriting the existing files
would add churn to a public history.

## Alternatives considered

- Move this repository to the A6.3 format for new decisions.
- Convert the existing decision files.

## Decided by

agent, under the maintainer's authorization to finish v0; the maintainer reviews it afterwards
