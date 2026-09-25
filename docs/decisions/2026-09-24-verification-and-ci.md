# Verification, acceptance, and CI

Date: 2026-09-24

## Decision

- Setup runs in two phases. Local generation needs no GitHub access and finishes first. GitHub
  provisioning follows as a separate step that can be resumed.
- Acceptance has three groups: local checks, agent smoke checks, and GitHub integration checks.
  Each check reports pass, fail, or not-tested. Missing prerequisites produce not-tested, never
  pass.
- This repository's CI generates each fixture project and runs the full build on synthetic data.
  A generated project's CI only renders the paper from committed outputs and runs the checks. A
  failed run does not update the preview artifacts, which are kept separate from the milestone tags
  that the owner creates by hand.
- Agent behavior is checked manually before each release, and the result is recorded in the
  compatibility table.
- The build entry point is `uv run build.py <stage>`.

## Reason

A local script cannot see agent behavior or GitHub events, so a single check would overstate what
it tested. Local generation first means setup can be tested offline. A project's full build may need
data that CI must not hold. Synthetic data lets this repository exercise every stage without that
problem. Running agents in CI would need paid credentials in a public repository. Running the script
directly avoids packaging a console entry point.

## Alternatives considered

- A single script-based acceptance check.
- Create the GitHub repository before local generation.
- Run the full build in every project's CI.
- Run agents in scheduled CI with stored API keys.
- Package a `build` console-script entry point.

## Decided by

maintainer
