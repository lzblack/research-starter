# Template tree, placeholder quoting, and the docx reference document

Date: 2026-09-24

## Decision

- The template tree has `base/` (always copied), `if-<flag>/` and `if-not-<flag>/` overlays
  (copied according to a derived flag), and `parts/` (per-section and provenance templates). Only
  `.tmpl` files are processed; other files are copied byte for byte.
- Conditional blocks may be negated (`@@if not <flag>@@`) and may nest.
- A placeholder written inside double quotes becomes an escaped double-quoted string that is valid
  YAML and TOML. YAML and TOML template files use only this form, so they remain parseable, and a
  test renders every template with hostile values.
- The template lockfile is produced by locking with a sentinel project name and restoring the
  placeholder (`tools/relock_template.py`).
- The template ships no docx reference document. Quarto's default styles apply until a project adds
  `paper/reference.docx`.

## Reason

Some files and some text exist only for one configuration (CODEOWNERS for teams, private-repository
wording for closed projects), and the earlier syntax could express neither. Escaping by position is
simpler and safer than escaping by file type, because one Markdown file can contain YAML front
matter. Pandoc's default reference document is licensed under the GPL, which the MIT-0 template
cannot carry, and rendering does not need it.

## Alternatives considered

- Conditional file names inside a single tree.
- Escaping values according to each file's extension.
- Shipping pandoc's default reference document, or authoring one for the template now.

## Decided by

maintainer
