# Changelog

All notable changes to this template are listed here. Versions are git tags. Each release that
changes template files includes migration notes that a project owner follows by hand.

## Unreleased

Pre-release development. Nothing here is a stable interface yet.

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
- CI for this repository on Linux (x86_64, aarch64) and macOS (arm64, x86_64), plus a
  public-content scan.
