"""Template syntax (appendix A1.4).

Order: conditional lines are resolved on the template text first. Then each remaining line is
either a list expansion or has its scalar placeholders substituted, in a single pass; inserted
text is never scanned again.
"""

import re
from dataclasses import dataclass, field

from starter.answers import quote

_NAME = r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*"
_IF = re.compile(rf"^@@if (not )?({_NAME})@@$")
_END = "@@end@@"
_LIST = re.compile(r"^([ \t]*)@@list:([a-z][a-z0-9-]*)@@[ \t]*$")
_SCALAR = re.compile(rf'"@@({_NAME})@@"|@@({_NAME})@@')


class TemplateError(Exception):
    """A defect in the template itself (not in the answers)."""


@dataclass
class Context:
    scalars: dict[str, str] = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)
    lists: dict[str, list[str]] = field(default_factory=dict)


def _resolve_conditionals(lines: list[str], ctx: Context, source: str) -> list[str]:
    out: list[str] = []
    stack: list[bool] = []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("@@if"):
            match = _IF.match(stripped)
            if match is None:
                raise TemplateError(f"{source}:{number}: malformed conditional {stripped!r}")
            negate, flag = match.groups()
            if flag not in ctx.flags:
                raise TemplateError(f"{source}:{number}: unknown flag {flag!r}")
            stack.append(ctx.flags[flag] != bool(negate))
        elif stripped == _END:
            if not stack:
                raise TemplateError(f"{source}:{number}: @@end@@ without @@if@@")
            stack.pop()
        elif all(stack):
            out.append(line)
    if stack:
        raise TemplateError(f"{source}: {len(stack)} unclosed @@if@@ block(s)")
    return out


def _substitute(line: str, ctx: Context, source: str, number: int) -> str:
    def replace(match: re.Match[str]) -> str:
        quoted, bare = match.groups()
        name = quoted or bare
        if name not in ctx.scalars:
            raise TemplateError(f"{source}:{number}: unknown placeholder {name!r}")
        value = ctx.scalars[name]
        return quote(value) if quoted else value

    return _SCALAR.sub(replace, line)


def render(text: str, ctx: Context, source: str) -> str:
    lines = _resolve_conditionals(text.splitlines(keepends=True), ctx, source)
    out: list[str] = []
    for number, line in enumerate(lines, start=1):
        body = line.rstrip("\n")
        newline = line[len(body) :]
        listed = _LIST.match(body)
        if listed:
            indent, name = listed.groups()
            if name not in ctx.lists:
                raise TemplateError(f"{source}:{number}: unknown list {name!r}")
            out.extend((indent + item if item else item) + "\n" for item in ctx.lists[name])
        else:
            out.append(_substitute(body, ctx, source, number) + newline)
    return "".join(out)
