# Markdown line breaks in this repository

Date: 2026-10-04

## Decision

Markdown prose in this repository is written one paragraph or list item per line; editors soft-wrap it. Prose is not hard-wrapped at a fixed column. The existing documents were reflowed in one formatting-only commit, listed in `.git-blame-ignore-revs`. A test (`tests/test_docs_wrapping.py`) checks tracked Markdown outside `template/`. Decision files dated before this one keep their original wrapping, because decision files are not edited. Files under `template/` are content for generated projects and follow their own conventions; the one-sentence-per-line rule for paper section files is unchanged.

## Reason

Line breaks inside a paragraph do not change the rendered output, so fixed-column wrapping only affects the source. Rewrapping after an edit spreads a small change over several lines of diff. One line per paragraph is a common convention, needs no tooling to maintain, and matches how issue and pull request text must be written, since GitHub renders single line breaks there. A rule that is invisible in rendered output is easy to break unnoticed, so a test enforces it.

## Alternatives considered

- Keep wrapping at about 100 columns, the previous unwritten convention.
- One sentence per line (semantic line breaks), as generated papers do; it gives the finest diffs but is rarely used for documentation and is harder to keep consistent.
- A written rule without a test.

## Decided by

maintainer
