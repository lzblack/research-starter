# research-starter: Normative Appendix (v0)

Status: draft for maintainer review. This appendix fixes the interfaces that implementation depends
on (PRD section 3a). It states interfaces and rules, not implementation. Where it and the PRD
disagree, the PRD wins and the disagreement is a defect to fix here.

Conventions:

- "Must" and "must not" are requirements. A rule that no check enforces is marked "(guideline)" and
  listed in A7.5 (PRD section 2, principle 3).
- Paths are POSIX, relative to the root of the generated project unless stated otherwise.
- "Template repository" means this repository; "project" means a generated project.
- Text files written by setup, build, or skills are UTF-8 without BOM, use LF line endings, and end
  with a newline.
- Identifier patterns are regular expressions matched against the whole value.
- "Tracked" means present in the git index.
- Milestones M1 to M6 are the milestone issues #3 to #8.

Contents: A1 setup CLI and answers schema; A2 configuration matrix; A3 determinism and reruns;
A4 output and provenance contract; A5 build semantics; A6 record formats; A7 check matrix;
A8 bibliography interface; A9 ownership and sign-off; A10 preview artifacts and milestone releases;
A11 toolchain, platforms, and agent compatibility.

## A1. Setup CLI and answers schema

### A1.1 Invocation

The setup script is `new_project.py` at the root of the template repository. It is run from a
checkout of the template repository, as `uv run new_project.py <command> [options]`, with no
packaged console entry point (the same convention as `build.py`). It never prompts; the agent
collects answers and writes the answers file (PRD section 4).

| Command | Purpose | Phase |
|---|---|---|
| `generate --answers FILE --target DIR [--date YYYY-MM-DD] [--dry-run] [--allow-dirty]` | create or complete a project | local generation |
| `accept --target DIR [--github]` | run the acceptance checks (PRD section 16) and report each result | local, then GitHub |
| `provision --target DIR --remote URL [--first-task TEXT]...` | add the remote, push, create the initial issues | GitHub provisioning |

Options:

- `--answers FILE`: the answers file (A1.3). Required for `generate`.
- `--target DIR`: the project directory. It must already exist (PRD section 4, step 1).
- `--date YYYY-MM-DD`: the generation date written into dated records. Default: the current local
  date on a first run, and the recorded date on a rerun. It is recorded in `project.yml` (A1.3). On
  a rerun, an explicit `--date` that differs from the recorded date is a precondition failure.
  Fixture runs pass it explicitly (A3.1).
- `--dry-run`: print the plan (A1.2) and exit with the code a real run would return, writing
  nothing. The agent shows this plan before writing (PRD section 4, step 4).
- `--allow-dirty`: permit a template checkout with uncommitted changes. The recorded template
  version then carries a `-dirty` suffix. Without this option a dirty checkout is a precondition
  failure. Intended for template development only.
- `--github` (for `accept`): also run the GitHub integration checks. Without it, those checks
  report not-tested.
- `--remote URL` (for `provision`): the URL of the empty GitHub repository the user created.
- `--first-task TEXT` (for `provision`, repeatable): the title of a project-specific first issue the
  user names (PRD section 4, step 8).

### A1.2 Output and exit codes

Every command writes one line per planned or performed action to standard output, prefixed by a
fixed verb, followed by a repository-relative path or a check identifier:

- `generate`: `create <path>`, `same <path>` (exists with identical bytes), `conflict <path>`
  (exists with different bytes, or is a directory or symbolic link; left unchanged).
- `accept`: `pass <check-id>`, `fail <check-id>`, `not-tested <check-id>`, each followed by a short
  reason for fail and not-tested.
- `provision`: `done <step>`, `skip <step>` (already done), `fail <step>`.

Errors and warnings go to standard error as `error: <location>: <message>` or
`warning: <location>: <message>`. The location is an answers field path (for example
`people[1].github`), a file path, or `-`.

| Code | Meaning | Files written |
|---|---|---|
| 0 | success; for `generate` this includes a rerun that changed nothing | as reported |
| 1 | unexpected internal error | possibly some; a rerun completes the project (A3.2) |
| 2 | usage error (unknown command or option) | none |
| 3 | answers file invalid | none |
| 4 | `generate`: conflicts found; `accept`: at least one check failed; `provision`: a step failed | `generate`: missing files created, conflicting files untouched |
| 5 | precondition failed (A1.5) | none |

### A1.3 Answers file

The answers file is YAML, parsed under the YAML 1.2 core schema with a safe loader: no tags, no
anchors or aliases, and duplicate keys are an error. Each value must have the type the schema
declares; there is no coercion. For example, `slug: 2024` is an error because the value is an
integer, and `language: no` is the string `no`. Unknown fields are an error.

`generate` saves the normalized answers (A3.1) in the project as `project.yml`, adding one mapping
that the answers file must not contain:

```yaml
generated:
  date: "2026-01-31"         # the --date value
  template_commit: "<sha>"   # with -dirty if applicable
```

Top-level field `schema` (integer, required) is the answers schema version. v0 defines version 1;
any other value is an error.

| Field | Type | Required | Default | Validation |
|---|---|---|---|---|
| `schema` | integer | yes | | `1` |
| `name` | string | yes | | 1-120 characters, one line |
| `slug` | string | yes | | `^[a-z][a-z0-9-]{1,48}[a-z0-9]$`, no `--` |
| `description` | string | no | `""` | at most 500 characters, one line |
| `language` | string | no | `en` | BCP 47 tag, `^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$` |
| `type` | string | no | `paper` | `paper` or `report` |
| `mode` | string | yes | | `solo` or `team` |
| `visibility` | string | yes | | `open` or `closed` |
| `people` | list of person | yes | | at least one entry; see below |
| `modules` | mapping | no | `{}` | must be empty in schema 1 (A2.1) |
| `writing.formats` | list of string | no | `[docx, pdf]` | non-empty, unique, each `docx` or `pdf` |
| `writing.csl` | string | no | `""` | empty, or a path to a `.csl` file relative to the answers file's directory (A8.3) |
| `writing.sections` | list of string | no | from `type` (A2.3) | non-empty, unique, each `^[a-z][a-z0-9-]{0,39}$` |
| `writing.human_drafted` | list of string | no | `[]` | each an entry of `writing.sections` |
| `reviewer_persona` | string | no | template default | at most 2000 characters |
| `data.large_store` | string | no | `""` | empty, a path starting with `~/`, or a URI whose scheme is not `file`; absolute paths are rejected because they often contain a user name |
| `review_gates` | list of string | no | `[]` | unique, each `^[a-z][a-z0-9-]{0,39}$` |
| `project_rules` | string | no | `""` | at most 10000 characters |

Each `people` entry:

| Field | Type | Required | Validation |
|---|---|---|---|
| `name` | string | yes | 1-120 characters, one line; unique across people after NFC and case folding |
| `github` | string | see below | `^[A-Za-z0-9](?:[A-Za-z0-9]\|-(?=[A-Za-z0-9])){0,38}$`; unique across people, ignoring case |
| `role` | string | yes | `lead`, `contributor`, or `reader` (A9.1) |
| `owns` | list of path pattern | no | see A1.4; not allowed for `reader` |
| `reviews` | list of path pattern | no | see A1.4; not allowed for `reader`; requires `github` |
| `consent_open` | boolean | when `visibility: open` | must be `true` for every person, readers included |

Cross-field rules:

- Exactly one person has role `lead`, and it is the first entry.
- In team mode, `lead` and `contributor` entries require `github`. A reader must not have
  `github`; a collaborator with a GitHub account is a contributor.
- `mode: solo` requires exactly one non-reader person. `mode: team` requires at least two.
- Each `owns` pattern matches at least one section file (A2.3), and each section file is matched by
  the `owns` patterns of at most one person (A9.2).

### A1.4 Template syntax and safe handling of answer values

Answer values are data. They are never passed to a shell, never evaluated as template expressions,
and never used as a path without validation.

Template tree:

- `template/base/` is always copied.
- `template/if-<flag>/` is copied when the flag (A2.1) is true, and `template/if-not-<flag>/` when
  it is false. A path produced by two of these directories is a template error.
- `template/parts/` holds per-item templates: `section.qmd.tmpl`, rendered once per section into
  `paper/sections/<id>.qmd`, and `template-provenance.md.tmpl`, rendered into the template
  provenance record (A6.3).
- Only files ending in `.tmpl` are processed, and they are written without that suffix. A file
  ending in `.symlink` holds a relative target inside the project; setup creates a symbolic link
  to it without the suffix. Every other file is copied byte for byte with its executable bit.
  Symbolic links in the template tree itself are template errors.

Template files use three constructs, applied in this order:

1. Conditional blocks: lines `@@if <flag>@@` or `@@if not <flag>@@`, closed by `@@end@@`, keep the
   enclosed lines only when the condition holds. Blocks may nest. No other expressions exist.
   Conditionals are resolved on the template text before any answer value is inserted.
2. List expansions: a line consisting only of optional indentation and `@@list:<name>@@` is replaced
   by the lines in the table below, each with that indentation, in the stated order. An empty list
   produces no lines.
3. Scalar placeholders: `@@<name>@@` is replaced by the value. A placeholder written directly
   inside double quotes, `"@@<name>@@"`, is replaced together with its quotes by a double-quoted
   string with the value escaped, which is valid in both YAML and TOML. YAML and TOML template files
   use only this quoted form. A bare placeholder is replaced by the value as written.

List expansion and scalar substitution happen in one pass over each line, and inserted text is
never scanned again, so a value containing `@@...@@` stays literal.

Scalar names are the answer fields (for example `name`, `slug`, `writing.csl`,
`data.large_store`), `generated.date`, `generated.template_commit`, `template.url`, `lead.name`,
and `lead.github`. The section template also has `section.id` and `section.title` (the ID with
hyphens as spaces and the first letter in upper case), and the flags `section.first` and
`section.human_drafted`.

| List | One item per | Line format | Order |
|---|---|---|---|
| `authors` | person | YAML list item with the person's name, quoted | `people` order |
| `section-includes` | section | `{{< include sections/<id>.qmd >}}` followed by an empty line | `writing.sections` order |
| `human-drafted` | human-drafted section | Markdown bullet with the section ID | `writing.sections` order |
| `review-gates` | gate | Markdown bullet with the gate ID | `review_gates` order |
| `codeowners` | distinct `reviews` pattern | `<pattern> @<handle> ...` listing every person who reviews exactly that pattern | first appearance in `people` order, then pattern order |

`project_rules` is inserted verbatim between fixed begin and end marker lines in `AGENTS.md`.

Path patterns (`owns`, `reviews`, dataset `paths`):

- They are non-empty and repository-relative. They use `/` separators and contain only
  `[A-Za-z0-9._/*-]`.
- They contain no `..` segment and do not start with `/`.
- They contain a `/` before their last character, so under CODEOWNERS rules they are anchored at
  the repository root.
- `*` and `**` have their CODEOWNERS meanings.

### A1.5 Preconditions and target rules

`generate` fails with code 5, writing nothing, when:

- git or uv is missing from `PATH`;
- the files setup reads (`template/`, `starter/`, `new_project.py`) have uncommitted changes and
  `--allow-dirty` is not given;
- the target does not exist, or lies inside the template checkout;
- the target has no `project.yml` and contains entries other than `.git/`, `.DS_Store`, and
  leftover temporary files of an interrupted run, since adding the template to an existing project
  is adoption mode (deferred, PRD section 19a);
- the target's git repository already has commits and no `project.yml`;
- the target has a `project.yml` whose answers differ from the normalized answers, or whose
  `generated` values differ from this run's template commit or explicit `--date` (A3.2).

`generate` writes `project.yml` first. If the target has no git repository, `generate` initializes
one with the unborn default branch `main`; an existing repository without commits is switched to
`main`. It sets `core.hooksPath` to `.githooks` (A7.1). It adds
every path it reports as `create` or `same` to the index. It does not commit; the agent makes the
initial commit after the local acceptance checks pass (PRD section 4, step 6).

### A1.6 Acceptance runs

`accept` creates a new git repository in a temporary directory, copies the target's tracked files
into it, and adds them to its index, so "tracked" means the same there. It runs the local checks in
that copy and never changes the target. The checks are listed in A7.3.

### A1.7 GitHub provisioning

`provision` performs these steps in order. Each step checks whether it is already done and skips
it if so, so an interrupted run is resumed by running it again.

1. Confirm that the target has at least one commit and that its local acceptance checks pass.
2. Add the remote as `origin`. An existing `origin` with the same URL is a skip; a different URL is
   a failure that is reported, never overwritten.
3. Push `main`. Never force-push.
4. Create the initial issues: complete setup, plus one per `--first-task`. Each issue body carries a
   hidden marker `<!-- research-starter:setup-issue:<key> -->`, where the key is `setup` or the
   first 12 hexadecimal digits of the SHA-256 of the task title. An existing issue with the same
   marker, open or closed, means that issue is skipped.
5. Run the GitHub integration checks (`accept --github`).

Required access: an authenticated GitHub CLI session with permission to push (including workflow
files) and to create issues in the repository. The exact token scopes are verified in M5 and
recorded in the compatibility file (A11.4).

`provision` and `accept` run from a template checkout at the recorded template commit. The bootstrap
instructions keep the temporary checkout until provisioning completes, or check out the recorded
commit again.

## A2. Configuration matrix

### A2.1 Derived flags

| Flag | Derived from | Value |
|---|---|---|
| `collaboration` | `mode` | true if `team`, false if `solo` |
| `open` | `visibility` | true if `open` |
| `docx`, `pdf` | `writing.formats` | true if the format is listed |
| `csl` | `writing.csl` | true if non-empty |
| `human_drafted` | `writing.human_drafted` | true if non-empty |
| `review_gates` | `review_gates` | true if non-empty |
| `large_store` | `data.large_store` | true if non-empty |

In schema 1 the collaboration module is derived from `mode` and cannot be set on its own. `modules`
stays in the schema for modules added later and must be empty.

### A2.2 Mode and visibility

| | solo | team |
|---|---|---|
| people | one non-reader (the lead), any number of readers | lead plus at least one contributor, any number of readers |
| collaboration module | off | on. Adds CODEOWNERS (A9.3), `meetings/` with `meetings/raw/` gitignored, the meeting-notes skill, and the issue-only discussion rule in `AGENTS.md` |
| branches | optional (README explains) | expected (README explains) |

| | open | closed |
|---|---|---|
| consent | `consent_open: true` for every person, readers included | not asked |
| README | states that the repository, including `journal/` if tracked, is public, and how to gitignore `journal/` | states that the repository stays private and that any public release is prepared manually |
| `AGENTS.md` | includes the rule never to bypass the pre-commit hook | pre-commit hook installed; bypass rule not included |
| gitignored by default | `meetings/raw/`, `private/` (people-related notes, pointers to non-public data), `logs/`, `.env`, `.build/`, `paper/_output/` | same |

The user chooses the visibility of the GitHub repository when creating it (PRD section 4, step 7).

### A2.3 Project type

`type` has one effect: it chooses the default for `writing.sections` when that field is absent.
An explicit `writing.sections` always wins.

| type | default `writing.sections` |
|---|---|
| paper | `introduction`, `data`, `methods`, `results`, `conclusion` |
| report | `summary`, `background`, `methods`, `findings`, `conclusion` |

Each section becomes `paper/sections/<id>.qmd`, included by `paper/paper.qmd` in list order.

### A2.4 Where each answer lands

| Answer | Observable effect |
|---|---|
| `name`, `description` | README title and summary; paper title; `pyproject.toml` description |
| `slug` | `pyproject.toml` and `uv.lock` project name; rendered file names (A5.4) |
| `language` | `AGENTS.md` language rule; `lang` in `paper/_quarto.yml` |
| `people` | `project.yml`; paper author list (editable); section owners (A9.2); CODEOWNERS in team mode |
| `writing.formats` | `format` entries in `paper/_quarto.yml`; the files `build.py paper` must produce; preview contents |
| `writing.csl` | copied CSL file and `csl` key (A8.3) |
| `writing.sections` | section files and include order |
| `writing.human_drafted` | list in `AGENTS.md`; a comment at the top of each such section file |
| `reviewer_persona` | the reviewer skill's persona file |
| `data.large_store` | data README |
| `review_gates` | README list of gates; sign-off records (A9.4) |
| `project_rules` | the marked block in `AGENTS.md` |

After setup, `project.yml` remains the project's configuration record, and checks read it (A7).
Files derived from it at setup, such as CODEOWNERS, `paper/_quarto.yml`, and the section files, are
not regenerated when it is edited. A person who edits it also updates those files by hand
(guideline).

### A2.5 Invalid combinations

Each of these is an answers error (code 3):

- solo with more than one non-reader, or team with fewer than two non-readers;
- open without every person's consent;
- a reader with `github`, `owns`, or `reviews`;
- `reviews` without `github`;
- `human_drafted` naming an unknown section;
- a section owned by two people, or an `owns` pattern that matches no section;
- a non-empty `modules`;
- duplicate names or GitHub handles.

## A3. Determinism boundary and rerun behavior

### A3.1 Determinism

Inputs: the template commit, the normalized answers, the `--date` value, and the content of the CSL
file if `writing.csl` is set.

Normalization: parse the answers file (A1.3), apply defaults, apply Unicode NFC to strings, reduce
`writing.csl` to its file name, and serialize in schema field order in block style with comments
dropped. Two answers files that differ only in formatting, comments, key order, omitted defaults,
or the directory of the CSL file normalize to the same bytes.

Guarantee: with equal inputs, two `generate` runs into two empty directories report the same set of
paths. The files at those paths have byte-identical contents and identical executable bits. The
template repository's CI tests this for every fixture (A7.4).

Outside the comparison boundary: anything not reported by `generate`, such as the contents of
`.git/`, `.venv/` created later by `uv sync`, and ignored files. Also outside it are filesystem
timestamps and ownership.

Rules that make this hold:

- Generated files must not contain the current time (other than `--date`), host names, user names,
  absolute paths, environment variables, or random values, except where an answer value itself
  supplies such text. Identifiers created by setup use fixed suffixes (A6.3).
- `uv.lock` is copied from the template, with the project name filled in both `pyproject.toml` and
  `uv.lock`. Setup never resolves dependencies. The local acceptance check `env-sync` confirms that
  `uv sync --locked` succeeds.
- Setup never downloads anything. The CSL file comes from the user (A8.3).

### A3.2 Reruns

A rerun is `generate` on a target that already has `project.yml`.

- It requires the same normalized answers and the same template commit as recorded in
  `project.yml`, and uses the recorded date. Otherwise it stops with code 5 and writes nothing.
  - Configuration changes after setup are made by hand (A2.4).
  - Template updates follow the documented manual migration (PRD section 17).
- For every path the run would produce:
  - if the path is absent, the file is created;
  - if it is present with identical bytes, it is reported `same`;
  - otherwise it is reported `conflict` and left unchanged.

  There is no overwrite option. To regenerate a file, the user deletes it and reruns.
- A rerun deletes no file except its own leftover temporary files.
- Exit code 0 if there were no conflicts, 4 otherwise. A rerun of a complete, unedited project
  reports only `same` lines and exits 0.
- Each file is written atomically, so an interrupted run leaves only complete files. Because
  `project.yml` is written first, a rerun can complete a project whose first run was interrupted.
- Git initialization, hook configuration, and adding paths to the index are skipped when already
  done.
- `provision` deduplicates its external actions (A1.7).

## A4. Output and provenance contract

### A4.1 Producers and locations

A producer is a notebook listed in the analyze stage (A5.2). Its producer ID is the file stem;
producer IDs are unique. Build runs every producer with the repository root as working directory,
so producers use repository-relative paths.

Producers write paper inputs to the output root given by the environment variable
`BUILD_OUTPUT_DIR`. When the variable is unset, as in an interactive session, the output root is
`.build/scratch/outputs/`. Producers do not write to `paper/outputs/` directly (guideline); the
analyze stage promotes outputs there (A5.3).

Under the output root a producer writes:

- `variables/<producer-id>.yml`, `tables/<artifact-id>.md`, and `figures/<artifact-id>.png`;
- `inputs/<producer-id>.json`: a JSON list of the repository paths the producer read, and of
  `dataset:<dataset-id>` entries for declared datasets (A4.5).

The inputs file is read by build and is not promoted. A producer without an inputs file has
declared no inputs. Build records the output root's contents after each step. A file created or
changed by a step is attributed to that step, and a step that changes a file attributed to an
earlier step fails the stage. A rewrite with identical bytes is not detected. The template ships a small helper that writes these files;
using it is a guideline.

Committed layout after a successful analyze stage:

| Path | Content |
|---|---|
| `paper/outputs/variables/<producer-id>.yml` | the variables written by one producer |
| `paper/outputs/tables/<artifact-id>.md` | one table |
| `paper/outputs/figures/<artifact-id>.png` | one figure |
| `paper/outputs/manifest.json` | provenance manifest (A4.3) |
| `paper/_variables.yml` | all variables merged, read by Quarto |

The template ships the example's outputs in this layout, so a new project renders before any
analysis is run. The example's prepared input is a small synthetic file committed under `data/`,
so its analyze stage runs without the prepare stage.

### A4.2 Artifact kinds

Artifact IDs match `^[a-z][a-z0-9_]{0,63}$` and are unique across all kinds and producers. A
duplicate ID fails the analyze stage.

- Variable: a YAML mapping entry `<id>: <value>` whose value is a string, integer, or boolean.
  Numbers meant for prose are written as already formatted strings (for example `"0.42"`); build
  does not format numbers. The paper references a variable with `{{< var <id> >}}`.
- Table: a Markdown pipe table followed by a caption line `: <caption> {#tbl-<id>}`. The paper
  includes it with `{{< include outputs/tables/<id>.md >}}` and cites it as `@tbl-<id>`.
- Figure: a PNG file. The paper embeds it with `![<caption>](outputs/figures/<id>.png){#fig-<id>}`
  and cites it as `@fig-<id>`. The caption belongs to the paper. PNG is the only figure format in
  v0 because it is the one tested in both output formats (A11.3).

### A4.3 Provenance manifest

`paper/outputs/manifest.json` is written by the analyze stage as JSON with sorted keys, two-space
indentation, and a final newline:

```json
{
  "artifacts": [
    {
      "file": "paper/outputs/variables/main.yml",
      "id": "n_obs",
      "inputs": [
        {"path": "data/derived/sample.parquet", "sha256": "<hex>"},
        {"path": "dataset:survey_2020", "version": "2020-03"}
      ],
      "kind": "variable",
      "producer": "notebooks/main.py",
      "producer_sha256": "<hex>",
      "sha256": "<hex>"
    }
  ],
  "schema": 1,
  "variables_sha256": "<hex>"
}
```

- `kind` is `variable`, `table`, or `figure`.
- `sha256` is the hash of the artifact file for tables and figures, and of the producer's variables
  file for variables.
- `inputs` lists the producer's declared inputs, each with its hash at the time of the run. A
  declared dataset outside the repository is listed as `dataset:<dataset-id>` with the `version`
  from its declaration, or `null` if none is declared. Reads the producer did not declare are not
  detected.
- `variables_sha256` is the hash of `paper/_variables.yml`.
- Every file under `paper/outputs/` except the manifest appears in the manifest, and every manifest
  entry's file exists.

### A4.4 Crosswalk

The check stage writes `.build/reports/crosswalk.csv`, with one row per reference to a variable,
table, or figure. Its columns are:

- `location`: `file:line` in the paper sources;
- `reference`: the reference as written;
- `artifact_id`, `kind`, and `producer`.

The file is regenerated on every check run and is not committed by default.

### A4.5 Dataset declarations

Datasets are declared in the YAML front matter of `data/README.md`, under the key `datasets`. The
Markdown body keeps the human description, including sources, access, and licenses in prose, and a
`## Data availability statement` section (PRD section 14). Each entry:

| Field | Type | Required | Rule |
|---|---|---|---|
| `id` | string | yes | `^[a-z][a-z0-9_-]{0,63}$`, unique |
| `tier` | string | yes | `public`, `licensed`, `confidential`, or `restricted` (PRD section 13) |
| `license` | string | yes | SPDX identifier, a license name, or `unknown` |
| `raw` | boolean | yes | true for raw data |
| `paths` | list of path pattern | no | repository paths where the dataset lives or would be placed (A1.4) |
| `location` | string | no | where it is held outside the repository, for example in the large store |
| `version` | string | no | version or access date, recorded in the manifest for producers that use it |

v0 accepts only public, synthetic, or owner-approved derived inputs (PRD section 13). A dataset
declared with tier confidential or restricted records that such data exists upstream, and check
`declared-paths` then covers its paths. Tier and license are declared separately, and the most
restrictive rule applies (PRD section 13).

## A5. Build semantics

### A5.1 Command

`uv run build.py <stage>`, where stage is `all`, `prepare`, `analyze`, `paper`, or `check` (PRD
section 14a). `check` also accepts `--staged`, which limits the data-exposure checks to staged
files, for the pre-commit hook (A7.1). CI invokes `uv run --locked build.py <stage>`, so an
outdated lockfile fails the run instead of being re-resolved.

### A5.2 Stage configuration

The ordered steps of the prepare and analyze stages, and the outputs of external jobs, are declared
in `pyproject.toml`. The paths below are illustrative. The template example declares no `external`
entries, so the example builds without any external job:

```toml
[tool.research-starter.build]
prepare = ["scripts/prepare_sample.py"]
analyze = ["notebooks/main.py"]

[tool.research-starter.build.external]
"data/raw/responses.parquet" = "scripts/fetch_responses.py"
```

- Steps run in list order, each as a separate process in the project environment, with the
  repository root as working directory. Researchers add a step by adding its path to the list.
- Notebooks run as `python <notebook>`, which stops at the first failing cell and exits non-zero
  (A11.3).
- `external` maps each output of a job outside build (data acquisition, paid API calls) to the
  script that produces it.

### A5.3 Stage behavior

| Stage | Requires | Does | Succeeds when |
|---|---|---|---|
| prepare | every `external` path exists | runs the prepare steps | every step exits 0 |
| analyze | every `external` path exists | runs the analyze steps with `BUILD_OUTPUT_DIR` set to a fresh staging directory under `.build/`, then validates and promotes | every step exits 0 and validation passes |
| paper | `paper/_variables.yml` and `paper/outputs/manifest.json` exist | renders every configured format into a staging directory under `.build/`, then promotes | Quarto exits 0 for every format and every expected file exists |
| check | the paper sources | runs the checks in A7.2 | no check fails |

- Missing prerequisites: before prepare or analyze runs any step, build reports each missing
  `external` path with the script to run, as `missing: <path> (run <script>)`, and exits 3 (PRD
  section 14a). A step
  that finds any other input missing exits 3 and prints a line in the same form (guideline).
- Sequence: `all` runs prepare, analyze, paper, and check in that order. It stops at the first stage
  that does not succeed and reports the remaining stages as `not-run`.
- Single stages: a single stage runs only that stage. There are no implicit prerequisites and no
  dependency tracking (PRD section 14a).
- Analyze validation and promotion:
  - Validation checks that artifact IDs are unique, that the manifest covers every staged artifact
    file, and that file formats follow A4.2.
  - On success, the staged set replaces `paper/outputs/` as a unit. This removes outputs that are no
    longer produced. `paper/_variables.yml` is then rewritten from the merged variables.
  - On failure, `paper/outputs/` and `paper/_variables.yml` are left unchanged, and the staging
    directory is kept for inspection.
  - An interruption during promotion can leave `paper/outputs/` missing or out of step with
    `paper/_variables.yml`. The `manifest` check detects both.
- Paper promotion: the rendered files replace the previous set in `paper/_output/` only when every
  configured format succeeded. A partial render never updates `paper/_output/`.
- Code execution: `paper/_quarto.yml` sets `execute: enabled: false`, so rendering never runs code
  (PRD section 14).
- Prepare steps write their own outputs, and write each file atomically (guideline). The template
  example does so.

### A5.4 Reporting, logs, and exit codes

Build prints one line per stage: `stage <name>: pass`, `fail`, `missing-prerequisite`, or
`not-run`. Each step's standard output and error are written to `logs/<stage>/<step-id>.log`,
where the step ID is the file stem. `logs/` is not committed by default.

| Code | Meaning |
|---|---|
| 0 | every requested stage passed |
| 1 | a stage failed |
| 2 | usage error |
| 3 | a stage's prerequisites were missing, including a step that exited 3 |

Rendered files are named `<slug>.docx` and `<slug>.pdf` and are written to `paper/_output/`, which
is gitignored by default. Committing a rendered document is a release decision (PRD section 13).

## A6. Memory and accountability record formats

### A6.1 Common rules

- Record files are Markdown with YAML front matter. People are referred to by their `name` from
  `project.yml`.
- A random suffix is lowercase hexadecimal from a cryptographic random source.
- Dates in file names are local calendar dates, unless the format says UTC.
- The formats in this section are guidelines, apart from the checked `status-size`.

### A6.2 Journal

- Path: `journal/YYYY-MM-DDTHHMMZ-<6 hex>.md`, where the time is the session start in UTC. The file
  stem is the session ID.
- Front matter:
  - `session`: the session ID;
  - `author`;
  - `agent`: tool and version, as reported by the tool;
  - `model`: as reported, or `unknown`.
- Body headings, in order:
  - `## Done`;
  - `## Decisions`: links to decision files, or "None";
  - `## Open`;
  - `## Next`;
  - `## AI use`: what the agent did in this session, in one to three sentences.
- One file per session, not edited after the session ends.
- The handoff commit carries the trailer `Session: <session ID>`. It is made even when nothing else
  changed, for example when `journal/` is gitignored.

Coverage rule for session-start recovery (PRD section 10). A handoff commit is a commit whose
`Session:` trailer names a journal file present in the working tree. A commit is covered if it is a
handoff commit or an ancestor of one. Recovery reports:

- uncovered commits reachable from `HEAD` whose author matches the current git user;
- uncommitted changes.

Recovery is best effort. A squash merge that drops the trailers makes the squashed work appear
uncovered. When `journal/` is gitignored, only the local machine's entries count (PRD section 12).

### A6.3 Decisions

- Path: `docs/decisions/YYYY-MM-DD-<slug>-<4 hex>.md`. The slug matches
  `^[a-z0-9]+(-[a-z0-9]+)*$` and has at most 50 characters. The file stem is the decision ID.
- Front matter:
  - `id`;
  - `date`;
  - `decided_by`: a list of names;
  - `supersedes`: a list of decision IDs, possibly empty;
  - `kind`: `decision` or `sign-off`, default `decision`.
- Body headings: `## Decision`, `## Reason`, `## Alternatives considered`.
- A decision is superseded by a new file that lists it in `supersedes`. Old files are not edited.
- Records created by setup use the suffix `0000`. The template provenance record, which the PRD
  calls the first decision, is `docs/decisions/<generated.date>-template-provenance-0000.md`. It
  states the template repository URL, the template commit (with `-dirty` if applicable), and the
  answers schema version.

### A6.4 Status

- `docs/status.md` must not exceed 8000 bytes (check `status-size`).
- Only the lead edits it. In team mode, CODEOWNERS assigns it to the lead (A9.3).
- The consolidate skill edits `docs/status.md` only in a session run by the lead. In anyone else's
  session it presents the proposed changes for the lead to apply.

### A6.5 AI-use record

- A commit that contains agent-produced changes carries the trailer
  `AI-Assisted: <agent> (<model>)`. Trailers that agents add on their own may appear as well.
- The `## AI use` section of each journal entry is the per-session record.
- `docs/ai-use.md` is a summary for disclosure statements, refreshed by the consolidate skill. It is
  built from the committed `AI-Assisted:` trailers, plus any journal entries available locally.
  Headings: `## Tools`, `## What AI assistance covered`, `## Human-drafted sections`,
  `## Last refreshed`.

### A6.6 Workflow retro

- Path: `docs/retro/YYYY-MM-DD-<slug>-<4 hex>.md`, one entry per file.
- Front matter: `date`, `author`, and `kind`, which is `friction`, `bug`, `idea`, or `worked-well`.
- Body: what happened, and what would have helped.

### A6.7 Meeting notes (collaboration module)

- Raw transcripts and platform summaries go in `meetings/raw/`, which is gitignored by default.
- Distilled notes go in `meetings/YYYY-MM-DD-<slug>.md`.
  - Front matter: `date`, `attendees`, and `source`, which is `transcript`, `summary`, or `notes`.
  - Body headings: `## Decisions` and `## Action items`. Each action item links to its issue once
    the issue is created after confirmation.
- The distilled note is the record of the meeting (PRD section 10).

### A6.8 Claim audit

- Path: `docs/audits/YYYY-MM-DD-<slug>-<4 hex>.md`.
- Front matter: `date`, `commit` (the audited commit), `auditor` (agent and model).
- Body: one table with these columns:
  - `location` (`file:line`);
  - `claim` (a short paraphrase);
  - `evidence`;
  - `assessment`: `supported`, `unsupported`, or `overstated`;
  - `disposition`: `accepted`, `revised`, `rejected`, or `pending`;
  - `disposed_by`.
- The agent fills every column up to `assessment` and sets `disposition` to `pending`. A person
  fills the rest (PRD section 14).

### A6.9 Closure

- Path: `docs/closure.md`, created when the project ends (PRD section 18b).
- Front matter:
  - `date`;
  - `outcome`: `published`, `preprint`, `blog-or-data-app`, `merged`, `parked`, or `abandoned`;
  - `location`: a URL, DOI, or project name; required unless the outcome is parked or abandoned;
  - `reason`: required when the outcome is parked or abandoned;
  - `final_tag`: required when the outcome is published, preprint, or blog-or-data-app.

## A7. Check matrix

### A7.1 Results and where checks run

Each check reports `pass`, `fail`, `warn`, or `not-tested`:

- `not-tested` is used when a check's inputs are unavailable, for example when data is absent in
  CI. It is never counted as `pass`.
- `warn` exists only for project checks with severity "warn". It never changes an exit code.
- Acceptance checks (A7.3) report only `pass`, `fail`, or `not-tested` (PRD section 16).

Checks run in three places:

- The pre-commit hook `.githooks/pre-commit` runs `uv run build.py check --staged`. This runs the
  checks marked "hook" below on staged files.
  - `generate` enables the hook in the generating clone only, because `core.hooksPath` is local git
    configuration and is not cloned.
  - Other clones enable it with `git config core.hooksPath .githooks`. README and `AGENTS.md` give
    this command.
- `uv run build.py check` runs every check, on tracked files and the paper sources.
- CI in the generated project runs `paper` and then `check` (PRD section 14).

A pass means only what the "Establishes" column says. The data-exposure checks together report
"configured checks passed", not "no sensitive data exists" (PRD section 13).

Paper sources are the `.qmd` files under `paper/` and the files they include. Detection skips code
blocks, inline code, and comments. The exact matching rules for each check are fixed by that
check's test fixtures in the template repository.

### A7.2 Project checks

| ID | Rule | Detection | Severity | Where | Establishes |
|---|---|---|---|---|---|
| `var-resolve` | every variable reference resolves | each `{{< var k >}}` in the paper sources has a key in `paper/_variables.yml` | fail | check | references resolve; rendering does not catch this (A11.3) |
| `var-unused` | produced variables are used | keys in `paper/_variables.yml` never referenced | warn | check | the listing |
| `xref-resolve` | every cross-reference resolves | each `@tbl-`, `@fig-`, `@sec-`, or `@eq-` reference has a matching label in the paper sources | fail | check | labels resolve |
| `cite-resolve` | every citation key resolves | each citation key is in `paper/references.bib` | fail | check | keys resolve, not that sources support claims |
| `include-resolve` | included files exist | each `{{< include >}}` target exists | fail | check | files exist |
| `figure-resolve` | embedded images exist | each image path in the paper sources exists | fail | check | files exist |
| `manifest` | outputs match the manifest | A4.3 rules; artifact IDs unique; each artifact file matches its recorded `sha256`; `paper/_variables.yml` equals the merge of the variables files and matches `variables_sha256` | fail | check | outputs are covered by provenance records and consistent with each other |
| `output-freshness` | outputs reflect current producers and inputs | recorded `producer_sha256` and input hashes compared with current files | warn | check | a producer or input changed since the last analyze; absent inputs and inputs without a version report `not-tested` |
| `typed-number` | no result number typed by hand | numerals in section prose outside shortcodes, citations, cross-references, and headings, excluding years 1800-2100 | warn | check | a review aid; cannot tell results from other numbers |
| `quote-marked` | quotations are marked and located | each `.quote` span has `status="verified"` or `status="unverifiable"` and is followed by a citation with a locator | fail | check | the marking exists, not that the quotation is accurate |
| `bib-keys` | keys are valid and unique, one entry per work | keys not matching A8.1, duplicate keys (ignoring case), or duplicate normalized DOIs | fail | check | keys are valid; no duplicates |
| `bib-unverified` | unverified entries are reported | entries whose verification status is `unverified` (A8.2) | warn | check | the listing |
| `sentence-per-line` | one sentence per line | a sentence end followed by another sentence on the same line in section files, allowing common abbreviations | warn | check | a review aid |
| `status-size` | status stays small | `docs/status.md` at most 8000 bytes | fail | check | size only |
| `owners` | every section has one owner | A9.2 over `project.yml` and the section files | fail | check | ownership is defined |
| `datasets` | dataset declarations are well formed | the A4.5 schema over the front matter of `data/README.md` | fail | check | the declarations are well formed, not that they are true |
| `declared-paths` | no files at raw or non-public dataset paths | tracked files matching the `paths` of datasets with `raw: true` or a tier other than public | fail | hook, check | nothing is tracked at declared paths |
| `forbidden-types` | forbidden file types are not tracked | `*.duckdb`, `*.duckdb.wal`, `.env` (but not `.env.example`) | fail | hook, check | none of the listed types is tracked |
| `file-size` | no large files in git | tracked files over 10 MB (10,000,000 bytes) | fail | hook, check | size only |
| `secret-patterns` | named secret patterns are absent | the named patterns below | fail | hook, check | the named patterns do not match; other secrets may exist |
| `pii-scan` | likely personal identifiers are reviewed | email addresses and phone numbers in tracked text files, excluding `paper/references.bib` and `project.yml` | warn | hook, check | a review aid; does not find all identifiers |
| `hook-enabled` | the pre-commit hook is enabled | `core.hooksPath` is `.githooks` | warn | check | local configuration only; `not-tested` in CI |
| `no-claude-md` | `AGENTS.md` is the only instruction file | any tracked file named `CLAUDE.md`, except a root `CLAUDE.md` containing exactly the documented import line (A11.4) | fail | check | file presence |

Named secret patterns in v0:

- private key blocks (`-----BEGIN ... PRIVATE KEY-----`);
- AWS access key IDs;
- GitHub tokens (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`);
- Anthropic API keys (`sk-ant-`);
- OpenAI project API keys (`sk-proj-`);
- Google API keys (`AIza`);
- Slack tokens (`xox[abprs]-`);
- non-empty assignments to names ending in `_API_KEY`, `_SECRET`, or `_TOKEN` in `.env`-style
  lines.

The exact regular expressions are kept with the check and tested with fixtures.

### A7.3 Acceptance checks (PRD section 16)

`accept` runs the local group on every call and the GitHub group with `--github`. Local checks run
in a temporary copy of the tracked files (A1.6). Agent smoke checks are run by hand before each
release. `accept` always reports them `not-tested`, and their results are recorded in the
compatibility file (A11.4).

| ID | Group | Rule |
|---|---|---|
| `env-sync` | local | `uv sync --locked` succeeds |
| `example-build` | local | `build.py analyze` writes at least one variable, one table, and one figure, and `build.py paper` produces every configured format |
| `render-content` | local | each rendered file, as text extracted from the docx XML or the PDF text layer, contains the example variable's value, section headings that start with a number, the example table's cross-reference rendered as the table caption prefix followed by a number ("Table 1" in English), and no unresolved-reference markers (`?var:`, `?@`, a citation key followed by `?`) |
| `project-checks` | local | `build.py check` exits 0 |
| `template-provenance` | local | the template provenance record (A6.3) exists and names `generated.template_commit` |
| `agent-session-start` | agent | the agent confirms that `AGENTS.md` was loaded |
| `agent-handoff` | agent | handoff writes a journal entry, and a decision entry when given a decision to record |
| `gh-ci` | GitHub | the push to `main` triggered a CI run that rendered the paper and ran the checks. The check waits up to 30 minutes and reports `not-tested` if the run has not finished by then |
| `gh-preview` | GitHub | the successful run produced the preview artifact (A10.1); `not-tested` if `gh-ci` did not pass |

### A7.4 Template repository checks

Fixture CI (PRD section 17). For each fixture answers file, CI:

- runs `generate` twice into new directories and compares the results (A3.1);
- runs `build.py all` on synthetic data;
- runs `accept`.

Fixtures together cover:

- solo and team;
- open and closed;
- the formats docx only, pdf only, and both;
- `writing.csl` set and unset;
- with and without human-drafted sections and review gates;
- readers present;
- each project type.

Separate tests cover reruns (unchanged, interrupted, and with conflicts) and invalid answers (each
case in A2.5). A further test creates two journal entries for the same person on the same day
(PRD section 10).

Public-content scan (PRD section 17). It covers `template/`, fixtures, examples, and docs. It fails
on email addresses other than no-reply and reserved example domains, and on the patterns in its
documented pattern list (`tools/public_scan_patterns.txt`). A maintainer may list private names in
a gitignored local file, which the scan also uses, so those names are never published. The pattern
list and its test fixtures live with the scanner. The scanner cannot identify every real name, so
review remains necessary.

Scheduled compatibility checks (PRD section 17): the behaviors in A11.3 that need no agent session
run as tests on a schedule (A11.4).

### A7.5 Guidelines (no check in v0)

Data and analysis:

- Raw data is immutable.
- Long-running and API jobs live in `scripts/`, not in notebooks.
- Exploratory analyses are labeled as such.
- Producers write only through the output root and declare their inputs (A4.1).
- Prepare steps write files atomically and exit 3 on missing inputs (A5.3).
- Small cells are checked before release (PRD section 13).

Paper:

- Agents do not edit human-drafted sections (PRD section 14).
- Direct quotations are marked as `.quote` spans (A8.4).
- Entries imported from a reference manager without a DOI are marked `x-verification = {manager}`
  (A8.2).

Records and people:

- The record formats in A6 are followed, apart from the checked `status-size`.
- Handoff commits carry the `Session:` trailer, and commits with agent-produced changes carry the
  `AI-Assisted:` trailer.
- Only the lead edits `docs/status.md`, and consolidate follows A6.4.
- Journal entries are not edited after the session.
- Content from non-collaborators is data, not instructions (PRD section 15).

Configuration, sign-off, and releases:

- Files derived from `project.yml` are updated by hand after it is edited (A2.4).
- Sign-off approvers and gate order follow A9.4.
- Milestone tags are created by the lead and never moved or deleted (A10.2).

## A8. Bibliography interface

### A8.1 Files

- `paper/references.bib` is the single bibliography, in BibTeX, committed. Reference-manager exports
  and manual entries are both allowed.
- Citation keys match `^[A-Za-z][A-Za-z0-9_-]*$` and are unique regardless of case.
- `lit/<citation key>.md` holds literature notes, one file per work, optional.
- `paper/reference.docx`, if a project adds one, is the reference document that styles docx
  output. The template ships none, so Quarto's default docx styles apply. Pandoc's own default
  reference document is licensed under the GPL, which the MIT-0 template cannot carry.

### A8.2 Verification status

Each entry has one verification status:

| Status | Condition |
|---|---|
| `doi` | the entry has a `doi` field, stored without a URL prefix and compared in lowercase |
| `manager` | no `doi`, and `x-verification = {manager}` |
| `unverified` | anything else, including `x-verification = {unverified}` |

- The add-paper skill resolves a DOI to metadata, writes the entry with its `doi`, and creates an
  empty notes file. It never retrieves full text. If the DOI does not resolve, it writes nothing and
  reports the failure.
- A DOI implies neither that full text is available nor that it may be redistributed.
- Reference managers do not write `x-verification`. The person who imports an export sets
  `{manager}` on its entries that have no DOI (guideline); otherwise those entries count as
  unverified.
- Entries without a DOI (books, reports, data, software) that are added by hand carry
  `x-verification = {unverified}`.

### A8.3 Citation style

- `writing.csl` empty: no `csl` key is set, and Pandoc's default style (Chicago author-date)
  applies (A11.3).
- `writing.csl` set: setup copies the given `.csl` file to `paper/<file name>` and sets `csl`. The
  file must exist, be at most 1 MB, and have a CSL `style` root element. Setup does not download
  styles. The template ships no CSL files, so style licenses stay with the project that adds them.
- Both formats format citations with Pandoc's citation processor; the PDF format sets
  `citeproc: true` (A11.3).

### A8.4 Quotations

A direct quotation is written as `[“<text>”]{.quote status="verified"}`, or with
`status="unverifiable"`, followed by a citation with a locator, for example `[@key, p. 12]`.
`verified` means a person checked the text against the source page. Both render as ordinary quoted
text (A11.3). Check: `quote-marked`.

## A9. Ownership and sign-off model

### A9.1 Roles

| Role | Count | GitHub | Can own or review | Duties |
|---|---|---|---|---|
| lead | exactly 1 | yes in team mode | yes | edits `docs/status.md`; default owner; approves every sign-off |
| contributor | 0 in solo, at least 1 in team | yes | yes | owns and reviews what `project.yml` assigns |
| reader | any | no | no | reads delivered docx or PDF; comments are applied to the sources by the lead or a contributor (PRD section 9a) |

Every person, whatever the role, is a member for the consent rule of open projects (PRD
section 12).

### A9.2 Section ownership

- Each section file `paper/sections/<id>.qmd` has exactly one owner: the person whose `owns`
  patterns match it.
  - A file matched by no pattern is owned by the lead.
  - A file matched by two people's patterns is an answers error in setup and fails check `owners`.
- The owner can defend every claim in the section (PRD section 8). For human-drafted sections,
  edits are applied by a person, and agents produce critique only (guideline, PRD section 14).

### A9.3 Reviews

- In team mode, CODEOWNERS contains the `codeowners` list expansion (A1.4). It is followed by a
  final line `/docs/status.md @<lead handle>`, which takes precedence because CODEOWNERS applies
  the last matching line.
- Where patterns of different people overlap, GitHub uses only the last matching line. Setup reports
  such overlaps as warnings on standard error.
- CODEOWNERS requests reviews. It does not enforce approval unless branch protection requires code
  owner review. Setup does not configure branch protection, and its availability for private
  repositories depends on the GitHub plan (not verified). Review gates are manual (PRD section 3a).

### A9.4 Review gates and sign-off

- `review_gates` lists gates in order, and gates are signed in that order (guideline).
- A sign-off is a decision record (A6.3) with `kind: sign-off` and these additional front matter
  fields:
  - `gate`: the gate ID;
  - `commit`: the reviewed commit;
  - `approvers`: names. They must include the lead. In team mode they also include the owner of each
    section changed since the previous sign-off (guideline).
  - `evidence`: a list, for example the CI run URL for `commit`, a claim audit ID, or a preview
    artifact identifier.
- A sign-off applies only to its `commit`. A later commit needs a new sign-off before it is tagged.
- In solo mode the lead signs alone, and the record states that it is a self-review.

## A10. Preview artifacts and milestone releases

### A10.1 Preview artifacts

- When produced: by the generated project's CI on a push to `main`, only when the `paper` and
  `check` stages both pass. A failed run uploads nothing, and earlier previews stay as they were.
  Pull request runs render and check but upload no preview.
- Form: one GitHub Actions workflow artifact per run, named `paper-preview`. It contains:
  - the rendered file for each configured format;
  - `manifest.json` (A4.3);
  - `build-info.json`, with the commit, run ID, UTC time, template commit, and the versions of
    Quarto, Pandoc, Typst, Python, and uv.
- Latest preview: the artifact of the latest successful run on `main`. Retention follows the
  repository's artifact retention setting; setup does not change it.
- Status: previews are mutable working drafts and are not citable. They are never git tags or
  GitHub releases.
- Access: access follows GitHub's rules for workflow artifacts (to be verified in M5). Readers
  without GitHub receive documents manually (PRD section 9a).

### A10.2 Milestone releases

- A milestone release is an annotated git tag named `<gate>-v<n>`, for example `submission-v1`,
  with `n` counting from 1 per gate.
- The lead creates it by hand on the commit named in a sign-off record's `commit` field. The tag
  message names the sign-off record ID.
- Tags are never moved or deleted (guideline).
- A GitHub release on the tag, with rendered files attached, is optional and manual. Archival, for
  example deposit with a DOI, is manual (PRD section 12).

## A11. Toolchain, platforms, and agent compatibility

### A11.1 Supported platforms

| Platform | CI runner | Status |
|---|---|---|
| Linux x86_64 | `ubuntu-24.04` | supported; verified by fixture CI on 2026-09-24 |
| Linux aarch64 | `ubuntu-24.04-arm` | supported; verified by fixture CI and locally on 2026-09-24 |
| macOS arm64 | `macos-15` | supported; verified by fixture CI on 2026-09-24 |
| macOS x86_64 | `macos-15-intel` | supported; verified by fixture CI on 2026-09-24 |

Runner labels are taken from GitHub's documentation of hosted runners, checked on 2026-09-24.
Versioned labels are used instead of `-latest` labels, so the tested image changes only by a
deliberate edit. A platform counts as verified once the template repository's CI passes on it.
Windows is deferred (PRD section 19a).

### A11.2 Toolchain

| Component | Version | Provided by | Notes |
|---|---|---|---|
| git | 2.43.0 tested | user prerequisite | |
| uv | 0.12.18 tested; `required-version = ">=0.12.18"` | user prerequisite (official installer) | installs Python |
| Python | 3.14 (`.python-version`); `requires-python = ">=3.12"`; 3.14.7 tested | uv | see "Python version" below |
| Quarto | 1.10.18, pinned exactly as `quarto-cli==1.10.18` | uv, from PyPI | bundles Pandoc 3.10, Typst 0.15.1, Dart Sass 1.101.0, Deno 2.7.14; no LaTeX or browser needed |
| marimo | 0.25.0, locked | uv | |
| GitHub CLI | recorded in M5 | user prerequisite, for provisioning only | |

Quarto is installed through uv as the `quarto-cli` package. It meets PRD section 4's condition for
a packaged distribution on the evidence below, with these known limits:

- PyPI carries only a source distribution. On first install, its build step downloads the official
  release archive for the platform from GitHub, about 440 MB unpacked. That first install needs
  network access to GitHub.
- `uv.lock` pins the hash of the source distribution, not of the downloaded archive, and the package
  does not verify a checksum. The checksums published on the same release page protect only against
  transport corruption, not against a changed release.
- The package depends on `jupyter`, `nbclient`, and `wheel`, about 100 packages in total. v0 does
  not execute code in Quarto (A5.3).

Upgrading Quarto is a deliberate template change: bump the pin, rerun the behaviors in A11.3, and
update this section.

Python version:

- `.python-version` chooses the interpreter, and `requires-python` sets the range the lockfile
  covers. Without `.python-version`, uv uses an already installed interpreter within the range,
  such as an older system Python, rather than the newest release (E10). The template therefore pins
  the newest Python release whose scientific packages it has tested. uv downloads that version when
  it is missing, so a user who does not choose a version gets it without any action.
- The floor 3.12 is the lowest version that current releases of numpy and scipy support.
- Each template release may raise the pin after the new Python passes the template's tests. Existing
  projects keep their pin until their owner changes it.
- A user who needs another version switches as follows (E9). The generated README gives both
  procedures:
  - within the range: `uv python pin <version>`, then `uv sync`; the lockfile does not change;
  - below the floor: lower `requires-python` in `pyproject.toml`, run `uv lock`, then
    `uv python pin <version>` and `uv sync`; the lockfile changes.

  A project on another version is outside the tested configuration, so it reruns
  `uv run build.py all` after switching.

### A11.3 Verified behaviors

Verified on 2026-09-24 on Linux aarch64 (Ubuntu 24.04), with the versions in A11.2. The identifiers
below are used in the scheduled compatibility tests (A11.4).

- **E1. Package build.** The build script of the `quarto-cli` 1.10.18 source distribution
  downloads the release archive for its own version from GitHub and does not verify a checksum.
  It requests the macOS, Linux x86_64, or Linux aarch64 archive according to the platform. Only
  the Linux aarch64 archive was downloaded here.
- **E2. Installation through uv.**
  - With a cold cache, `uv add quarto-cli` in a fresh project took about 32 s, and `quarto check`
    passed.
  - With a warm cache, a second project ran `uv lock --offline`, `uv sync --offline`, and
    `quarto --version` successfully.
- **E3. Standalone archive.** The standalone archive for the same version matched its published
  checksum and contained the same Quarto and Typst versions.
- **E4. Rendering.**
  - The test project had:
    - `_variables.yml`;
    - numbered sections;
    - an included Markdown table with a `tbl-` label;
    - a PNG figure with a `fig-` label;
    - a local BibTeX file and a local CSL file;
    - a docx reference document.

    It rendered to docx and Typst PDF in about 2 s, with no font warnings. Both files contained the
    variable values, numbered headings, "Table 1", "Figure 1", and the formatted citation.
  - With Typst's own citation processor, the PDF bibliography differed in title case from the docx
    output for the same style. With `citeproc: true` it matched.
- **E5. Failure behavior.** Exit codes are given as docx / PDF.

  | Defect | Exit code | Output |
  |---|---|---|
  | unknown variable | 0 / 0 | text `?var:<key>` |
  | unknown cross-reference | 0 / 0 | text `?@tbl-<id>` |
  | unknown citation key | 0 / 1 with Typst's processor; 0 / 0 with `citeproc: true` | docx text `(<key>?)` |
  | missing include | 1 / 1 | no file |
  | missing figure | 0 / 1 | docx shows the description instead |

  When one format fails in a combined render, Quarto exits 1. It rewrites the other format's file
  and leaves the failed format's previous file in place.
- **E6. marimo.**
  - `python <notebook>` exits 1 when a cell raises, and execution stops at that cell. Files written
    before the failure remain.
  - `marimo export html` also exits 1, but it writes its HTML and keeps running cells that do not
    depend on the failed one.
  - Relative paths resolve against the working directory, not the notebook's directory.
- **E7. Syntax probes.** A crossref label with an underscore resolves. A `.quote` span renders as
  plain text. The unknown BibTeX field `x-verification` is ignored under both citation processors.
- **E8. Build and lockfile probes.**
  - Without `csl`, citations use Chicago author-date.
  - `quarto render --output-dir <dir>` writes every format and its resources into that directory.
  - With `execute: enabled: false`, a Python code cell is not run and rendering exits 0.
  - `sys.exit(3)` in a notebook cell run as `python <notebook>` gives exit code 3.
  - `uv sync --locked` passes after the project name is replaced in both `pyproject.toml` and
    `uv.lock`, and fails if only `pyproject.toml` changes.
- **E9. Switching Python.** The test project had `requires-python = ">=3.12"`, a pin of 3.14, and
  `quarto-cli`, marimo, numpy, and pandas as dependencies.
  - `uv python pin 3.12` followed by `uv sync --locked` succeeded, and the lockfile hash did not
    change. numpy, pandas, Quarto, and marimo ran on 3.12.
  - `uv python pin 3.11` was refused with an error naming `requires-python`.
  - After lowering `requires-python` to `>=3.11`, `uv lock` resolved an older numpy for 3.11. Then
    `uv python pin 3.11` and `uv sync --locked` succeeded, and every package ran on 3.11.16.
  - The wheel built from the `quarto-cli` source distribution is tagged `py3-none-any`, so a
    Python switch reuses the cached build.
- **E10. Interpreter choice.** With `requires-python = ">=3.12"`:
  - with a pin of 3.14, uv used 3.14.7;
  - with no pin and a uv-managed 3.14 installed, it used 3.14.7;
  - with no pin and only the system Python available (3.12.3, simulated with
    `UV_PYTHON_PREFERENCE=only-system`), it used 3.12.3;
  - with a pin of 3.13 and no 3.13 installed, `uv sync` downloaded and used 3.13.15.

Not exercised:

- a first install with GitHub unreachable (the package build script shows that the build then fails
  with an error unrelated to the download);
- macOS and Linux x86_64;
- uv versions other than 0.12.18;
- drift between the PyPI package and the GitHub release.

M1 CI covers the platforms. The rest remain open.

### A11.4 Compatibility file and per-agent table

The compatibility file required by PRD section 17 is `docs/compatibility.md` in the template
repository, created in M1. For each assumption about an external tool, it records:

- the assumption;
- how it is tested: a scheduled test, a manual smoke check, or not testable;
- the tested version;
- the last verification date.

The behaviors E1 to E10 are its first entries.

It also holds the per-agent table below, whose values are verified in M4 and not assumed (PRD
section 11). This appendix fixes only the table's fields. `tools/agent_smoke.py` runs the agent
smoke checks for one agent and checks the results against A6.

Skills are kept once, in `.agents/skills/`. Setup creates the link `.claude/skills ->
../.agents/skills` for agents that read only their own directory, so skills are read in place and
there are no copies to refresh.

| Field | Claude Code | Codex | pi (best-effort) |
|---|---|---|---|
| Instruction file discovery | unverified | unverified | unverified |
| Condition requiring the one-line `CLAUDE.md` import, and the exact import line | unverified | n/a | n/a |
| Skill discovery location | unverified | unverified | unverified |
| Invocation syntax | unverified | unverified | unverified |
| Skills read in place or copied; refresh method | unverified | unverified | unverified |
| Tested version | unverified | unverified | unverified |
| Smoke checks (`agent-session-start`, `agent-handoff`) | not-tested | not-tested | not-tested |
| Last verification date | none | none | none |
