---
name: add-paper
description: Add a paper to the bibliography from its DOI and create an empty notes file in lit/. Use when the user wants to cite or read a work with a DOI.
---

# Add paper

1. Run `uv run python .agents/skills/add-paper/add_paper.py <DOI>`. It fetches metadata from
   doi.org, adds the entry to `paper/references.bib` with a generated citation key, and creates
   `lit/<key>.md`.
   - If the DOI is already there, it reports the existing key.
   - If the DOI does not resolve, it writes nothing. Report the failure; do not invent metadata.
2. Tell the user the citation key to use, for example `@doe2020synthetic`.
3. Never download or store full text. A DOI does not mean the full text is available or may be
   redistributed.
4. A work without a DOI (a book, report, dataset, or software) may be added by hand only after
   the user confirms its metadata. Such entries carry `x-verification = {unverified}`, or
   `{manager}` when they come from a reference-manager export.
