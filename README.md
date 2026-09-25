# research-starter

> **Status: pre-release.** Design in progress; nothing is usable yet. Expect breaking changes.

A starter template for empirical research projects done with AI coding agents.
People make the research decisions; agents help with execution and checking.

The design is in [docs/design/PRD.md](docs/design/PRD.md). Feedback is welcome as issues.

## What it provides

A new project gets, from one answers file:

- a repository that people and agents share as the project record: `AGENTS.md` for agents, a
  journal entry per session, decisions, status, and GitHub issues;
- a build (`uv run build.py all`) that regenerates every number, table, and figure from the data
  and renders the paper with Quarto to docx and PDF (Typst), with a provenance manifest;
- checks that fail when a variable, citation, or cross-reference does not resolve, and checks for
  secrets and data at declared non-public paths;
- agent skills for handoff, consolidation, review, and adding papers, tested with Claude Code
  and Codex;
- CI that renders the paper and runs the checks, with preview artifacts.

## Quick start

Requirements: git and [uv](https://docs.astral.sh/uv/) on macOS or Linux. uv installs Python,
Quarto, and everything else.

1. Create an empty directory for your project.
2. Ask your coding agent to clone this repository to a temporary folder and follow
   [BOOTSTRAP.md](BOOTSTRAP.md). It asks the setup questions, shows the plan, creates the project,
   runs the acceptance checks, and can connect it to GitHub.

Or run the setup script yourself from a clone of this repository:

```
uv run new_project.py generate --answers answers.yml --target ../my-project --dry-run
uv run new_project.py generate --answers answers.yml --target ../my-project
uv run new_project.py accept --target ../my-project
```

The answers file format is defined in the design appendix (A1.3); the files in
`tests/fixtures/answers/` are examples.

## Non-goals

- Deciding what to research, or writing papers autonomously end to end.
- A hosted or web product.
- Stata, SPSS, and SAS: v0 does not provision or test proprietary runtimes. R is the leading
  candidate for the next version.
- Windows, in v0.

## Status and support

v0 is pre-release and is being piloted. Versions stay at 0.x until the pilots finish, and the
[CHANGELOG](CHANGELOG.md) lists changes. Supported platforms are Linux (x86_64, aarch64) and macOS
(arm64, x86_64); tested tools and agents are recorded in
[docs/compatibility.md](docs/compatibility.md).

## Licensing

This repository's own code is licensed [MIT](LICENSE). Everything under `template/`, which is
copied into new projects, is licensed [MIT-0](LICENSE-TEMPLATE): generated projects belong
entirely to their users, and no attribution is required. Each project chooses its own license.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). To report a security problem, see [SECURITY.md](SECURITY.md).
