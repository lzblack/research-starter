# Setup interface and configuration rules

Date: 2026-09-24

## Decision

- The setup script is `new_project.py` at the root of the template repository, run as
  `uv run new_project.py <command>`. It has the commands `generate`, `accept`, and `provision`,
  never prompts, and uses fixed exit codes.
- Answers are a strict YAML file with schema version 1. Unknown fields, duplicate keys, and
  values of the wrong type are errors. The normalized answers are saved in the project as
  `project.yml`, which remains the project's configuration record.
- Roles are lead, contributor, and reader. Opening a project requires the consent of every person
  listed, readers included.
- The collaboration module is derived from the mode: on for team projects, off for solo projects.
  It cannot be set on its own in schema 1. The PRD's setup table is updated accordingly.
- Setup installs the pre-commit hook in the generating clone. Other clones enable it with one
  documented command. In open projects `AGENTS.md` forbids bypassing it, and CI runs the same checks
  again. A check reports a warning when the hook is not enabled.
- The project type has one effect: it chooses the default list of paper sections.
- A rerun never overwrites or deletes files. It creates missing files and reports files that
  differ. It requires the same answers and the same template commit as the original run.
- Setup never commits; it adds the files it writes to the git index. Acceptance checks run on a
  temporary copy of the tracked files, so they never change the project.

## Reason

A script run through uv needs no packaged entry point, which matches the build entry point. Strict
parsing prevents silent misreadings such as a language code read as a boolean. Deriving the module
from the mode leaves no invalid combinations while v0 has only one module. Giving the type a single,
visible effect avoids undefined behavior without adding machinery. Readers are named co-authors,
and an open repository exposes their names and shared work, so their consent is needed as well. The
role name contributor avoids confusion with "member" in the sense of anyone on the team. A rerun
that never overwrites is safe after a partial setup. Configuration changes and template updates are
handled by hand in v0, so a rerun does not need to reconcile edited files. Git does not copy hook
configuration into clones, so a local hook cannot be guaranteed; CI repeats the checks, which keeps
the rule for open projects enforced where it matters.

## Alternatives considered

- Named `setup.py`, which is easily confused with the setuptools convention.
- Keep the collaboration module as an independent toggle, with the mode only supplying its default.
- Record the type without any effect in v0.
- Require consent only from people with GitHub accounts.
- Interactive conflict resolution, or an overwrite option on rerun.
- Fail the checks when the local hook is not enabled.

## Decided by

maintainer
