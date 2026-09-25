# Toolchain and supported platforms for v0

Date: 2026-09-24

## Decision

- Quarto is installed through uv as the `quarto-cli` package from PyPI, pinned to an exact version
  (1.10.18 at the time of writing). It is not a separate prerequisite. The user installs git and
  uv; uv provides Python, Quarto, Pandoc, and Typst.
- Generated projects pin Python through `.python-version` (3.14), allow `requires-python >= 3.12`,
  and require uv 0.12.18 or later. The generated README documents how to switch to another Python
  version. Template releases raise the pin once a newer Python passes the template's tests.
- Supported platforms are Linux x86_64, Linux aarch64, macOS arm64, and macOS x86_64. Each is a
  release gate once the template repository's CI runs on it. CI uses versioned runner labels, not
  `-latest` labels.
- Notebooks run headless as `python <notebook>`, not through `marimo export`.
- Rendering is staged and promoted as a complete set, and reference resolution is checked
  separately from rendering.
- Both output formats format citations with Pandoc's citation processor.
- Rendering disables code execution.

## Reason

Local experiments recorded in appendix A11 showed that the uv-installed package provides a working
Quarto with Pandoc and Typst included. It renders docx and Typst PDF without LaTeX. The version is
recorded in the lockfile, and with a warm cache it syncs offline. One `uv sync` then provides the
whole toolchain, which removes a setup step. The package has known limits, and appendix A11 states
them: the downloaded binary is not covered by the lockfile hash, and the first install needs access
to GitHub. A checksum published on the same release page would add little protection.

Without a pinned version, uv uses an interpreter that is already installed, which may be an old
system Python. A pin therefore gives users who do not choose a version the newest tested release,
which uv downloads when it is missing. The floor of 3.12 keeps the lockfile valid for versions that
current scientific packages support, so switching within that range needs no new lock.

GitHub-hosted runners exist for all four platforms, so each one can be tested.

The same experiments showed that Quarto exits successfully when a variable, cross-reference, or
citation does not resolve. They also showed that a failed combined render leaves the older file of
the failed format next to a fresh file of the other format. marimo's export command keeps running
cells after a failure, while running the notebook as a script stops at the first failing cell.
Typst's own citation processor formatted the same style differently from the docx output.

## Alternatives considered

- Standalone Quarto installation as a prerequisite, verified against the release checksum.
- Supporting only the three platforms without Intel macOS.
- No Python pin, or pinning the previous Python release.
- Running notebooks through `marimo export html`.
- Treating a zero exit code from rendering as proof that references resolve.

## Decided by

maintainer
