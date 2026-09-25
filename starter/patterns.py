"""Repository path patterns (appendix A1.4): anchored CODEOWNERS-style globs."""

import re

_ALLOWED = re.compile(r"^[A-Za-z0-9._/*-]+$")


def pattern_error(pattern: str) -> str | None:
    """Return why `pattern` is not a valid path pattern, or None if it is valid."""
    if not pattern:
        return "must not be empty"
    if not _ALLOWED.match(pattern):
        return "may contain only letters, digits, '.', '_', '-', '/', and '*'"
    if pattern.startswith("/"):
        return "must be relative (no leading '/')"
    if ".." in pattern.split("/"):
        return "must not contain a '..' segment"
    if "/" not in pattern[:-1]:
        return "must contain a '/' before its last character, so it is anchored at the root"
    return None


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Translate a valid pattern to a regex over repository-relative file paths.

    Semantics follow CODEOWNERS (gitignore) rules for anchored patterns: `*` matches within
    one segment, `**` across segments, and a pattern also matches everything below a
    directory it names.
    """
    body = pattern.rstrip("/")
    out = []
    i = 0
    while i < len(body):
        if body.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif body.startswith("**", i):
            out.append(".*")
            i += 2
        elif body[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(body[i]))
            i += 1
    # A pattern also covers everything below a directory it names, except when its last segment
    # has a single-segment wildcard: CODEOWNERS `docs/*` does not match nested files.
    last = body.rsplit("/", 1)[-1]
    below = "" if "*" in last and last != "**" else "(?:/.*)?"
    return re.compile("^" + "".join(out) + below + "$")


def matches(pattern: str, path: str) -> bool:
    return compile_pattern(pattern).match(path) is not None
