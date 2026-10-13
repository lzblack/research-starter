# Bootstrap: create a new research project

For an AI agent that a user asked to create a new project from this template. Agents working on this repository itself should ignore this file and follow AGENTS.md.

Work in the user's conversation language, but write the answers file and everything in the new project in the repository language the user chooses.

## 1. Preflight

Report every finding here, before asking any setup question.

1. Check the operating system with `uname -s`. `Darwin` (macOS) and `Linux` are supported. On anything else, including Windows (where `uname` may be missing or print `MINGW` or `CYGWIN`), stop and tell the user that v0 supports only macOS and Linux.
2. Check `git --version` and `uv --version` (0.12.18 or later). If uv is missing, offer the official installer (<https://docs.astral.sh/uv/getting-started/installation/>) and install it only with the user's consent.
3. Check `gh --version` and `gh auth status`. Connecting the project to GitHub (section 4) needs the GitHub CLI logged in with the `repo` and `workflow` scopes. If gh is missing, not logged in, or its listed scopes lack either one, tell the user now and offer the fix (`gh auth login`, or `gh auth refresh -s repo,workflow`). If no scopes are listed, as with a fine-grained token, say that they can be confirmed only during provisioning. Local generation does not need gh and continues either way.
4. In this checkout, run `uv sync --locked`.
5. The user provides the project directory (the target): either an empty directory, or a clone of a GitHub repository they just created, private for a closed project and public for an open one. The clone may contain the README, LICENSE, and .gitignore that GitHub adds when creating a repository; `generate` replaces README.md and .gitignore with the project's own and keeps LICENSE. Keep this checkout until GitHub provisioning is complete; `accept` and `provision` need the same template commit.

## 2. Ask the setup questions

Ask one question at a time, say what the default is, and explain a choice only when the user asks. Record the answers as YAML (schema 1, appendix A1.3) in a file outside the target:

| Field | Ask | Default |
|---|---|---|
| `name`, `slug`, `description` | the project's title, a short identifier (lowercase letters, digits, hyphens), and one sentence | description empty |
| `language` | the repository language, independent of this conversation | `en` |
| `type` | `paper` or `report` | `paper` |
| `mode` | `solo` or `team` | none; ask |
| `people` | each person's name, role (`lead` first, then `contributor` or `reader`), and GitHub handle; for teams, which section files each person owns and reviews | none; ask |
| `visibility` | `open` (public from day one) or `closed` (private permanently) | none; ask |
| `people[].consent_open` | for an open project, confirm that every person, readers included, consents | required when open |
| `writing.formats` | docx, pdf, or both | both |
| `writing.csl` | a citation style file the user provides, or none (Chicago author-date) | none |
| `writing.sections` | the paper's sections, in order | from `type` |
| `writing.human_drafted` | sections that people must draft themselves | none |
| `reviewer_persona` | who the reviewer skill should review as | the default persona |
| `data.large_store` | where large data lives: a `~/` path or a URI | none |
| `review_gates` | milestones that need sign-off, in order | none |
| `project_rules` | any rules to copy into the project's AGENTS.md | none |

## 3. Generate

1. For a clone, read the repository's visibility with `gh repo view <url> --json visibility -q .visibility`, or, without gh, ask the user whether GitHub shows it as Public or Private. An open project needs `PUBLIC` and a closed one `PRIVATE`; on a mismatch, stop and resolve it with the user (change the repository's visibility on GitHub, or the answer) before generating.
2. Show the plan and ask the user to confirm: `uv run new_project.py generate --answers <answers.yml> --target <dir> --dry-run`.
3. Run the same command without `--dry-run`.
   - On exit code 3, the answers are invalid: ask again about each reported field.
   - On exit code 4, files already exist and differ: report them; never delete the user's files.
   - Report any warnings.
4. Run `uv run new_project.py accept --target <dir>` and report every result. `not-tested` results are expected for the agent and GitHub checks.
5. In the target, make the initial commit, with the trailer `AI-Assisted: <tool> (<model>)`. The pre-commit hook runs the data-exposure checks.
6. Tell the user plainly that the project exists only on this computer and cannot be seen on GitHub yet (for a clone: GitHub still shows only its initial commit). Ask whether to connect it to GitHub now.

## 4. GitHub (can be resumed later)

1. If the target is not a clone, the user creates an empty GitHub repository, private for a closed project and public for an open one, with no README, license, or .gitignore: `provision` cannot push to a repository that has commits the project does not contain. If preflight found a problem with gh, the user fixes it now.
2. Run `uv run new_project.py provision --target <dir> --remote <url> [--first-task "<title>"]...` and report each step; for a clone, `<url>` is the repository it was cloned from. It is safe to rerun after an interruption.
3. Tell the user what to do next: open a new session in the project, where the agent follows the project's AGENTS.md.
