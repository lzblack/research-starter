# Markdown line breaks in template files

Date: 2026-10-04

## Decision

Markdown files under `template/` (`.md` and `.md.tmpl`) follow the repository rule: one paragraph or list item per line, no wrapping at a fixed column. This supersedes the exclusion of `template/` in `2026-10-04-markdown-line-breaks.md`. Lines that start with a template directive or placeholder (`@@`) are kept on their own lines. The test in `tests/test_docs_wrapping.py` now covers these files, and the reflow commit is listed in `.git-blame-ignore-revs`. The one-sentence-per-line rule for paper section files is unchanged. Generated projects get no rule or check for their own Markdown wrapping; that would be a template feature and needs a PRD change first.

## Reason

Generated projects otherwise start with hard-wrapped documentation while their maintainers and agents may follow one paragraph per line, which mixes two styles in one project. Template issue and skill text is also read in places where single line breaks may be rendered. The reflow changes no rendered text: every fixture project was generated before and after, and each changed Markdown file renders to the same HTML.

## Alternatives considered

- Keep template files wrapped at a fixed column, as decided earlier the same day.
- Also add a wrapping rule and check to generated projects.

## Decided by

maintainer
