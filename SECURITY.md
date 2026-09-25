# Security

This template sets up checks for secrets and for data at declared non-public paths. Those checks
report "configured checks passed"; they do not establish that no sensitive data exists (see
appendix A7 of the design).

## Reporting a problem

Report a security problem without public details. Examples: a check that misses a pattern it
claims to catch, a way the template could expose data or credentials, or a workflow that runs
untrusted code with write access. Open an issue titled "Security report" that contains no
technical details, and the maintainer will arrange a private channel. Please do not publish
details until a fix is available.

## Scope

Supported: the latest commit on `main`. The template is pre-release, so fixes are not backported.
