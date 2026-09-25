# Changelog

All notable changes to this template are listed here. Versions are git tags (`v0.x.y` until the
pilots finish).

Each release that changes template files has a "Migration" subsection. A project owner, or their
agent, applies it by hand:
1. Find the project's template commit in its template provenance record.
2. Follow the migration notes of every later release in order.
3. Record the new template version as a decision.

## Unreleased

### Added

- Generated projects explain how to change course: recording the change as a decision, updating
  the brief and status, and editing the configuration and the files derived from it by hand.

## 0.1.0 (2026-09-25)

The first release, for the pilots. Interfaces may still change before 1.0.

### Migration

None: this is the first release.

### Added

- Setup script `new_project.py` with `generate`, `accept`, and `provision`. It uses a versioned
  answers schema, deterministic output, and safe reruns.
- Build entry point `build.py` with the prepare, analyze, paper, and check stages, staged
  promotion of outputs, and a provenance manifest.
- A synthetic Python and marimo example that produces a variable, a table, and a figure.
- Project checks: reference resolution, output freshness, writing aids, bibliography,
  records, ownership, and data exposure. A pre-commit hook runs the data-exposure checks.
- Agent skills: handoff, consolidate, reviewer, add-paper, and meeting-notes, tested with
  Claude Code and Codex.
- GitHub provisioning, the generated project's CI, and preview artifacts.
- CI for this repository on Linux (x86_64, aarch64) and macOS (arm64, x86_64), a
  public-content scan, and weekly compatibility checks for the external tools.
- Guidance in generated projects: the working routine, writing syntax, data governance, review
  gates, milestone releases, claim audits, retro entries, template updates, and closure.
