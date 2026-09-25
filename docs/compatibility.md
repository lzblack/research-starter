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
Typst 0.15.1), marimo 0.25.0, git 2.43.0, GitHub CLI 2.45.0.

| ID | Assumption | Test | Last verified |
|---|---|---|---|
| E1 | The `quarto-cli` source distribution downloads the release archive for its own version and platform | planned (scheduled) | 2026-09-24 |
| E2 | `uv sync` installs a working Quarto from `quarto-cli`, and a warm cache syncs offline | fixture CI (`env-sync`) for installation; offline sync planned (scheduled) | 2026-09-24 |
| E3 | The standalone release archive matches its published checksum | planned (scheduled) | 2026-09-24 |
| E4 | Quarto renders docx and Typst PDF with variables, numbered sections, cross-references, a PNG figure, and citations, without LaTeX | fixture CI (`render-content`) | 2026-09-24 |
| E5 | Unresolved variables, cross-references, and citations do not make rendering fail; a combined render that fails leaves the other format's file | planned (scheduled) | 2026-09-24 |
| E6 | `python <notebook>` stops at the first failing marimo cell and exits non-zero; relative paths resolve against the working directory | successful runs: fixture CI (`build.py analyze`); failure behavior planned (scheduled) | 2026-09-24 |
| E7 | Underscore crossref labels resolve; `.quote` spans render as text; unknown BibTeX fields are ignored | planned (M3, check fixtures) | 2026-09-24 |
| E8 | Default citation style, `--output-dir` staging, disabled execution, notebook exit code 3, lockfile with a substituted project name | lockfile and `--output-dir`: fixture CI (`env-sync`, `build.py paper`); exit code 3: build unit tests with a plain script; the rest planned (scheduled) | 2026-09-24 |
| E9 | Switching Python within `requires-python` needs no new lock; below the floor needs `uv lock` first | planned (scheduled) | 2026-09-24 |
| E10 | Without `.python-version`, uv uses an installed interpreter within the range, not the newest release | planned (scheduled) | 2026-09-24 |
| E11 | An include inside an included section file resolves its path relative to the main document (`paper/`), not the section file | fixture CI (`render-content`) | 2026-09-24 |
| E12 | Pushing files under `.github/workflows/` with an OAuth token needs the `workflow` scope | manual (provisioning, M5) | 2026-09-24 |
| E13 | Claude Code reads `AGENTS.md` without `CLAUDE.md`; a `CLAUDE.md` containing `@AGENTS.md` imports it | manual (`tools/agent_smoke.py`) | 2026-09-24 |
| E14 | Claude Code loads project skills only from `.claude/skills/` and follows a directory link to `.agents/skills`; Codex loads `.agents/skills/` and runs `$<skill>` | manual (`tools/agent_smoke.py`) | 2026-09-24 |
| E15 | Codex's bubblewrap sandbox fails on Ubuntu 24.04 when unprivileged user namespaces are restricted by AppArmor | manual | 2026-09-24 |

## Per-agent table

Verified on 2026-09-24 on Linux aarch64 with `tools/agent_smoke.py` and the discovery experiments
recorded as E13 to E15.

| Field | Claude Code | Codex | pi (best-effort) |
|---|---|---|---|
| Instruction file discovery | reads `AGENTS.md` when no `CLAUDE.md` exists | reads `AGENTS.md` | not tested (not installed) |
| Condition requiring the one-line `CLAUDE.md` import, and the exact import line | none found in the tested configuration; the import line `@AGENTS.md` works | n/a | n/a |
| Skill discovery location | `.claude/skills/` only; a directory link `.claude/skills -> ../.agents/skills` works | `.agents/skills/` | not tested |
| Invocation syntax | `/<skill> [arguments]` | `$<skill> [arguments]` | not tested |
| Skills read in place or copied; refresh method | read in place through the link; new skills appear without copying | read in place | not tested |
| Tested version | 2.1.282 | codex-cli 0.156.1 | none |
| Smoke checks (`agent-session-start`, `agent-handoff`) | pass, pass | pass, pass | not-tested |
| Last verification date | 2026-09-24 | 2026-09-24 | none |

Notes:

- Codex's command sandbox (bubblewrap) could not start on Ubuntu 24.04 with
  `kernel.apparmor_restrict_unprivileged_userns = 1` (E15). Skill discovery and explicit
  invocation worked, but shell commands inside the sandbox failed. The smoke checks run Codex
  without its sandbox, inside a temporary project only.
- Claude Code reads user-level instructions from the home directory as well. Smoke results can
  reflect that configuration.
