# Data handling in v0

Date: 2026-09-24

## Decision

- v0 accepts only public, synthetic, or owner-approved derived inputs. Isolating sensitive data is
  the operator's responsibility. The template gives guidance only, and the principle "privacy by
  construction" is replaced by "approved inputs only".
- Each dataset declares a sensitivity tier and a license separately. Their constraints add up, and
  the most restrictive rule applies. Data in the licensed, confidential, and restricted tiers is
  never committed.
- Configured checks cover declared dataset paths, forbidden file types, file size limits, and named
  secret patterns, and report "configured checks passed". A PII pattern scan runs as a warning.
  Small-cell checking is guidance only.
- The owner reviews committed outputs, rendered documents, and any committed logs before release.
  `logs/` is not committed by default.
- Material that may not belong in a repository (meeting transcripts, people-related notes, pointers
  to non-public data) is gitignored by default. Open projects may also gitignore `journal/`. The
  generated README explains the options, and each project adjusts the defaults.

## Reason

An agent that has the same filesystem permissions can still reach data kept outside the working
tree, so the template cannot guarantee isolation. File checks and pattern scanners also cannot prove
that a file contains nothing sensitive, so the checks only claim what they actually test. Without
the cumulative rule, a dataset that is both licensed and sensitive would get conflicting
instructions. A PII scan catches common mistakes but misses some and flags others wrongly, so it
warns and does not block. Logs can reveal paths, values, or credentials. Projects differ in
visibility and privacy needs, so a safe default with guidance serves them better than one fixed
rule.

## Alternatives considered

- Keep physical isolation as a template guarantee, or provision an isolated environment in v0.
- Make the PII scan blocking, or enforce small-cell suppression by check.
- Commit logs by default.
- Never commit non-public material, with no project-level adjustment.

## Decided by

maintainer
