# Compatibility file

Every assumption the template makes about external tool behavior is listed here (PRD section 17,
appendix A11.4). Each entry records how it is tested, the tested version, and the last
verification date. The evidence for E1 to E10 is described in appendix A11.3.

Test methods:

- **fixture CI**: exercised by every run of the template repository's CI (appendix A7.4).
- **scheduled**: to run in a scheduled workflow that needs no agent session.
- **manual**: checked by hand before each release and recorded here.
- **planned**: not yet automated; the milestone that adds it is named.

## Platforms

| Platform | CI runner | Status | Last verified |
|---|---|---|---|
| Linux x86_64 | `ubuntu-24.04` | verified (fixture CI) | 2026-09-24 |
| Linux aarch64 | `ubuntu-24.04-arm` | verified (fixture CI and locally) | 2026-09-24 |
| macOS arm64 | `macos-15` | verified (fixture CI) | 2026-09-24 |
| macOS x86_64 | `macos-15-intel` | verified (fixture CI) | 2026-09-24 |

## Tool assumptions

Tested versions: uv 0.12.18, Python 3.14.7, quarto-cli 1.10.18 (Quarto 1.10.18, Pandoc 3.10,
Typst 0.15.1), marimo 0.25.0, git 2.43.0.

| ID | Assumption | Test | Last verified |
|---|---|---|---|
| E1 | The `quarto-cli` source distribution downloads the release archive for its own version and platform | planned (scheduled) | 2026-09-24 |
| E2 | `uv sync` installs a working Quarto from `quarto-cli`, and a warm cache syncs offline | fixture CI (`env-sync`) for installation; offline sync planned (scheduled) | 2026-09-24 |
| E3 | The standalone release archive matches its published checksum | planned (scheduled) | 2026-09-24 |
| E4 | Quarto renders docx and Typst PDF with variables, numbered sections, cross-references, a PNG figure, and citations, without LaTeX | fixture CI (`render-content`) | 2026-09-24 |
| E5 | Unresolved variables, cross-references, and citations do not make rendering fail; a combined render that fails leaves the other format's file | planned (scheduled) | 2026-09-24 |
| E6 | `python <notebook>` stops at the first failing marimo cell and exits non-zero; relative paths resolve against the working directory | planned (M2, build tests) | 2026-09-24 |
| E7 | Underscore crossref labels resolve; `.quote` spans render as text; unknown BibTeX fields are ignored | planned (M3, check fixtures) | 2026-09-24 |
| E8 | Default citation style, `--output-dir` staging, disabled execution, notebook exit code 3, lockfile with a substituted project name | lockfile: fixture CI (`env-sync`); the rest planned (M2) | 2026-09-24 |
| E9 | Switching Python within `requires-python` needs no new lock; below the floor needs `uv lock` first | planned (scheduled) | 2026-09-24 |
| E10 | Without `.python-version`, uv uses an installed interpreter within the range, not the newest release | planned (scheduled) | 2026-09-24 |
| E11 | An include inside an included section file resolves its path relative to the main document (`paper/`), not the section file | fixture CI (`render-content`) | 2026-09-24 |
| E12 | Pushing files under `.github/workflows/` with an OAuth token needs the `workflow` scope | manual (provisioning, M5) | 2026-09-24 |

## Per-agent table

Values are verified in M4, not assumed (PRD section 11).

| Field | Claude Code | Codex | pi (best-effort) |
|---|---|---|---|
| Instruction file discovery | unverified | unverified | unverified |
| Condition requiring the one-line `CLAUDE.md` import, and the exact import line | unverified | n/a | n/a |
| Skill discovery location | unverified | unverified | unverified |
| Invocation syntax | unverified | unverified | unverified |
| Skills read in place or copied; refresh method | unverified | unverified | unverified |
| Tested version | unverified | unverified | unverified |
| Smoke checks (`agent-session-start`, `agent-handoff`) | not-tested | not-tested | not-tested |
| Last verification date | none | none | none |
