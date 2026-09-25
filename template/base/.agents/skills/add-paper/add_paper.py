"""Add a work to paper/references.bib from its DOI, and create its empty notes file.

    uv run python .agents/skills/add-paper/add_paper.py 10.1000/example

The metadata comes from doi.org. Full text is never retrieved. If the DOI does not resolve,
nothing is written.
"""

import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BIB = ROOT / "paper" / "references.bib"
LIT = ROOT / "lit"
DOI = re.compile(r"^10\.\d{4,9}/\S+$")
STOPWORDS = {"a", "an", "the", "on", "of", "in", "and", "for", "to", "with", "from", "at", "by"}


def normalize_doi(value: str) -> str:
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", value.strip(), flags=re.I).lower()


def fetch(doi: str) -> str:
    request = urllib.request.Request(
        f"https://doi.org/{urllib.parse.quote(doi, safe='/')}",
        headers={"Accept": "application/x-bibtex; charset=utf-8", "User-Agent": "research-starter add-paper"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fields(entry: str) -> dict[str, str]:
    """Top-level fields of one BibTeX entry, with braces and quotes removed."""
    found: dict[str, str] = {}
    body = entry[entry.index(",") + 1 :] if "," in entry else ""
    i = 0
    while True:
        match = re.compile(r"\s*,?\s*([A-Za-z][\w-]*)\s*=\s*").match(body, i)
        if not match:
            break
        i = match.end()
        if i < len(body) and body[i] == "{":
            depth, start = 0, i
            while i < len(body):
                depth += {"{": 1, "}": -1}.get(body[i], 0)
                i += 1
                if depth == 0:
                    break
            value = body[start + 1 : i - 1]
        elif i < len(body) and body[i] == '"':
            end = body.index('"', i + 1)
            value, i = body[i + 1 : end], end + 1
        else:
            end = re.compile(r"[,}\s]").search(body, i)
            value, i = body[i : end.start() if end else len(body)], end.start() if end else len(body)
        found[match.group(1).lower()] = re.sub(r"[{}]", "", value).strip()
    return found


def ascii_word(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", folded.lower())


def make_key(meta: dict[str, str], existing: set[str]) -> str:
    first_author = meta.get("author", "").split(" and ")[0].strip()
    last = first_author.split(",")[0] if "," in first_author else (first_author.split() or [""])[-1]
    title_words = [ascii_word(w) for w in meta.get("title", "").split()]
    word = next((w for w in title_words if w and w not in STOPWORDS), "")
    base = f"{ascii_word(last) or 'anon'}{meta.get('year', '')}{word}"
    if not base[0].isalpha():
        base = "ref" + base
    key, suffix = base, ord("a")
    while key.lower() in existing:
        key, suffix = f"{base}{chr(suffix)}", suffix + 1
    return key


def existing_entries(text: str) -> tuple[set[str], dict[str, str]]:
    keys, dois = set(), {}
    for match in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,", text):
        keys.add(match.group(1).lower())
        end = text.find("\n@", match.end())
        doi = fields(text[match.start() : end if end != -1 else len(text)]).get("doi")
        if doi:
            dois[normalize_doi(doi)] = match.group(1)
    return keys, dois


def add(raw_doi: str, fetcher=fetch) -> tuple[int, str]:
    doi = normalize_doi(raw_doi)
    if not DOI.match(doi):
        return 1, f"error: {raw_doi!r} is not a DOI (expected 10.<registrant>/<suffix>)"
    current = BIB.read_text(encoding="utf-8") if BIB.exists() else ""
    keys, dois = existing_entries(current)
    if doi in dois:
        return 0, f"already in paper/references.bib as {dois[doi]}; nothing written"
    try:
        entry = fetcher(doi).strip()
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
        return 1, f"error: could not resolve {doi}: {exc}; nothing written"
    if not entry.startswith("@"):
        return 1, f"error: doi.org returned no BibTeX for {doi}; nothing written"
    meta = fields(entry)
    key = make_key(meta, keys)
    entry = re.sub(r"^@(\w+)\s*\{[^,]*,", lambda m: f"@{m.group(1).lower()}{{{key},", entry, count=1)
    if "doi" not in meta:
        entry = entry.rstrip().rstrip("}").rstrip().rstrip(",") + f",\n  doi = {{{doi}}}\n}}"
    BIB.parent.mkdir(parents=True, exist_ok=True)
    separator = "" if not current or current.endswith("\n\n") else ("\n" if current.endswith("\n") else "\n\n")
    BIB.write_text(current + separator + entry + "\n", encoding="utf-8")
    notes = LIT / f"{key}.md"
    if not notes.exists():
        LIT.mkdir(exist_ok=True)
        title = meta.get("title", "").replace('"', "'")
        notes.write_text(f'---\nkey: {key}\ndoi: "{doi}"\ntitle: "{title}"\n---\n\n## Notes\n', encoding="utf-8")
    return 0, f"added {key}"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    code, message = add(sys.argv[1])
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
