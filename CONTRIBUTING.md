# Contributing

This template is pre-release. The design is in [docs/design/PRD.md](docs/design/PRD.md), and the
interfaces are fixed in [docs/design/PRD-appendix.md](docs/design/PRD-appendix.md).

## Feedback

Feedback is welcome as issues. Use the issue templates for bug reports, feature requests, and
feedback from using the template in a project. Features that are deferred are listed in the PRD's
"Later" section. Propose a change to that list rather than opening an issue for a deferred feature.

## Pull requests

Open an issue before a pull request, so the change can be checked against the PRD first. Pull
requests from outside contributors may be declined while the design is changing. No workflow that
invokes an AI agent runs on pull requests from outside contributors.

A pull request must keep CI passing:

```
uv sync --locked
uv run --locked pytest -m "not fixtures and not compat"   # unit tests
uv run --locked pytest -m fixtures                        # generate, accept, and build every fixture
uv run --locked tools/public_scan.py                      # public-content scan
uv run --locked pytest -m compat -o addopts=""            # external tool behaviors (network; weekly in CI)
```

## Content rules

- Everything in the repository is in English.
- Template content, fixtures, examples, and documentation contain no private identities
  (personal names, email addresses, institutions) and no non-synthetic research examples.
  Examples use synthetic data. Required attribution, license notices, citation metadata, and
  names of public tools and projects are allowed.
- Files under `template/` are licensed MIT-0 ([LICENSE-TEMPLATE](LICENSE-TEMPLATE)). By
  contributing to them you agree to that license. Third-party files keep their own license notice
  and source.
