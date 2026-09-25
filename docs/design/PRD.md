# research-starter: Product Requirements (v0)

Status: draft for pilot. Implementation happens in this repo; this document states what to build
and why, not how. Section 3a defines what v0 builds; section 19a lists what is deferred. Deferred
items are not requirements.

## 1. Purpose

A project template for AI-native empirical research. It sets up a repository in which people and
coding agents (Claude Code and Codex are tested; others that read AGENTS.md may work) can work on
one research project with shared memory, reproducible outputs, and verification built in.

Target work: quantitative social science and business research (econometrics, survey and text
data, event studies, panel methods), with optional ML experiments. Not limited to one discipline.

Target users: a solo researcher, or a team of researchers. Differences in responsibility are
expressed through roles, not through a special mode.

The template is open source and public from v0. Generated projects are independent of it at
runtime; the template is used only at creation and when migrating to a newer template version.

## 2. Design principles

1. **The repository is the authoritative shared project record.** Agent-local memory is not relied
   on for team continuity.
2. **Evidence before prose.** Every empirical claim in the paper references generated output (a
   variable, table, or figure) or a citation. A resolved reference is a mechanical check; whether
   the evidence supports the claim is a human-reviewed assessment (section 14).
3. **Checks, not prompts.** Rules that matter are enforced by scripts, hooks, or CI that can reject
   work. A rule with neither a check nor a real incident behind it is marked as a guideline, so no one
   mistakes it for protection. Rules that are routinely broken get relaxed, not ignored.
4. **Copy, don't generate.** Setup copies finished template files and fills placeholders. The agent
   does not author scaffold files from descriptions, so the same answers produce the same repo (the
   comparison boundary is defined in the normative appendix).
5. **Approved inputs only.** v0 accepts only public, synthetic, or owner-approved derived inputs.
   The template does not isolate sensitive data; that is the operator's responsibility, and the
   template provides guidance only (section 13).
6. **Open by default where possible.** Visibility is a per-project choice (section 12).
7. **Language-neutral output contract.** Analysis code, in any language, produces only three kinds
   of paper inputs: `_variables.yml`, table files, and figure files. The paper and the checks read
   these and never depend on the analysis language. v0 ships Python only; adding a language means
   adding its environment setup and examples, not changing the contract.
8. **Keep it simple.** No hosted services, no heavy multi-agent orchestration, minimal dependencies.
   Every file in the template must answer "which real problem does this solve?"

## 3. Non-goals

- Deciding what to research (idea evaluation, feasibility screening). Upstream tools may create
  projects from this template, but that logic lives outside it.
- Generating papers autonomously end to end. Writing with agent help is in scope: the template
  provides the substrate (traceable numbers, verified citations, owned sections, critique) and
  can host third-party writing skills, but does not ship its own drafting pipeline.
- A hosted or web product.
- Discipline-specific journal profiles or style packs.
- Stata, SPSS, and SAS. v0 does not provision or test proprietary runtimes; the supported CI
  environment uses Python. Users may still run them locally, but no template support or checks are
  provided.
- R in v0. R is the leading candidate for the next version (see section 19).

## 3a. v0 scope

v0 builds only the following. Anything else in this document that is not listed here is either
supporting detail for these items or deferred (section 19a).

- Deterministic new-project setup with one versioned answers schema, safe reruns, clear errors, and
  a declared platform and toolchain matrix. Supported platforms: macOS and Linux.
- Solo and small-team configurations, section ownership, GitHub issues, and documented manual review
  gates.
- A tested Python/marimo example producing variables, a table, and a figure; an explicit output and
  provenance contract; ordered build stages with reliable failure handling.
- Quarto rendering from committed, approved outputs in a non-empty subset of docx and PDF (Typst),
  defaulting to both; one bibliography interface.
- Repository instructions and manually invoked handoff and consolidation procedures, tested with
  Claude Code and Codex; pi is best-effort. Behavioral instructions are guidance, not enforcement.
- Public or private working repositories using public, synthetic, or owner-approved derived inputs,
  with dataset declarations, secret, path, and size checks, and explicit limits on what those checks
  establish.
- Synthetic full-build CI in this repository; render-and-check CI in generated projects. Preview
  artifacts are kept separate from manually approved milestone releases.
- Delivery to readers without GitHub, public export, and archival are manual.
- Essential public-repository licensing, contribution and security documentation, a changelog, and
  a small defined pilot measurement plan.

Interfaces that implementation depends on (setup CLI and answers schema, configuration matrix,
determinism and rerun behavior, output and provenance contract, build semantics, memory record
formats, check definitions, bibliography interface, ownership and sign-off model, preview artifacts,
and the supported toolchain versions) are fixed in a normative appendix before implementation
starts.

## 4. Setup flow

Setup runs in two phases. Local generation needs no GitHub access and completes first; GitHub
provisioning follows as a separate, resumable step.

Local generation:

1. User creates an empty local directory for the project.
2. User asks their agent to clone this template to a temporary folder and follow `BOOTSTRAP.md`.
3. Agent runs a preflight check. Required locally: git and uv (uv installs Python). If uv is
   missing, the agent offers the official installer. Quarto is installed through uv if a reliable
   packaged distribution is confirmed; otherwise it is a separate prerequisite.
4. Agent asks the setup questions (section 5), one at a time, and shows the full plan before writing.
5. Agent copies template files, fills placeholders, removes disabled module content, and records
   the template commit hash as the first decision in `docs/decisions/`.
6. Agent runs the local acceptance checks (section 16), reports each result, and makes the initial
   commit.

GitHub provisioning:

7. User creates an empty GitHub repository (private or public) and authenticates; the agent adds it
   as the remote and pushes.
8. Agent creates the initial issues: complete setup, and any project-specific first tasks the user
   names.
9. Agent runs the GitHub integration checks (section 16) and reports each result.

Setup must be safe to rerun: rerunning on a partially set-up repo detects existing files and does
not overwrite them silently (exact rerun behavior is defined in the normative appendix).

Setup has a deterministic, scriptable core: a script takes an answers file and produces the
project. The agent's role is to collect answers, call the script, and handle errors. This makes
setup testable in CI with fixture answer files (section 17) and keeps agents from improvising
scaffold content.

Copier or a similar templating tool is out of scope for v0 (section 19a).

## 5. Setup questions

| Field | Values | Notes |
|---|---|---|
| name, slug, description | text | |
| language | repository language | default English; independent of the conversation language |
| type | paper, report | |
| people | name, GitHub handle (optional), role, `owns` paths, `reviews` paths | first person is the lead; role `reader` for collaborators without GitHub |
| mode | solo, team | team enables the collaboration module |
| visibility | open, closed | see section 12; open requires every member's consent |
| modules | see section 9 | each on/off |
| writing.formats | non-empty subset of docx, pdf (Typst) | default: docx and pdf |
| writing.csl | any CSL style | |
| writing.sections | ordered list | one file per section |
| writing.human_drafted | list of sections, default empty | protected sections for institutional rules; see section 14 |
| reviewer persona | text | used by the reviewer command |
| data.large_store | path or URI | |
| review_gates | ordered list | milestones needing sign-off |
| project_rules | free text | copied verbatim into AGENTS.md |

Answers are saved in the generated repo.

## 6. Generated repository

```
AGENTS.md            the only agent instruction file (no CLAUDE.md)
README.md            human onboarding and template mechanics
build.py             single entry point for regenerating results and the paper (section 14a)
pyproject.toml, uv.lock
docs/                brief, status, decisions/ (one file each), ai-use, workflow-retro, closure
journal/             append-only session notes, one file per session
logs/                run logs written by scripts; not committed by default
data/                small derived data; README with sources, tiers, licenses
scripts/             batch jobs (fetch, parse, API calls), cached and resumable
notebooks/           marimo notebooks: analysis, figures, paper inputs
paper/               Quarto project
lit/                 literature notes
.agents/skills/      agent skills (section 11), made available to each supported agent
.github/             workflows, issue templates, CODEOWNERS (team mode)
```

Optional local rule files: `data/AGENTS.md` and `paper/AGENTS.md`, only where rules are genuinely
local.

## 7. Documentation roles

- **README.md** is for humans: what the project is, setup, and how to use the template's mechanics
  (session loop, where work goes, writing syntax). Project-specific routines (meeting cadence,
  review rhythm, milestones) are added by the team after setup, not by the template.
- README explains, in plain language, why the routine exists: issues are the shared to-do list for
  people and agents; branches are a safe sandbox that can be discarded or reviewed before merging
  (optional for solo users); handoff writes to the repository, which is the authoritative shared
  project record, so continuity does not depend on any one agent's local memory.
- README also explains why each session should cover one issue and end with handoff followed by a
  fresh session. The working hypothesis, to be checked in the pilots, is that context pressure comes
  mainly from within a session (code, data samples, tool output accumulate and degrade agent
  performance), not from stored memory. Handoff saves what matters to the repo so the context can be
  cleared safely.
- **AGENTS.md** is for agents: session start procedure, repository map, commands, rules, memory
  protocol. Imperative, short, no rationale. Agents answer workflow questions from README rather
  than inventing procedures.
- Claude Code reads AGENTS.md when no CLAUDE.md exists (v2.1.277+). A one-line CLAUDE.md importing
  AGENTS.md is allowed only as a documented exception for platforms or configurations where this
  fallback does not apply; the per-agent compatibility table (section 11) records which.

## 8. Core rules (always on)

Data: raw data immutable; parquet as storage format; DuckDB only for ad hoc queries, `.duckdb`
files never committed; secrets only in `.env`; files over 10 MB not in git; `logs/` not committed
by default, because logs can reveal paths, data values, or credentials.

Analysis: long-running and API jobs in `scripts/`, never in notebooks; notebooks run headless and
regenerate their outputs; exploratory analyses labeled as such.

Paper: no result number typed by hand (numbers via `_variables.yml`, tables via include, figures
from files); every citation key resolves; bibliography entries come from DOI or reference-manager
metadata where possible, and entries without such metadata (books, reports, data, software) are
allowed but marked unverified and reported by check; quotations are verified against the source
page, or marked unverifiable when the source cannot be obtained, never invented; one sentence per line.

Generated measurements: outputs of LLM or other model-based measurement are produced by scripts
and, once produced, stored as data of record with model, prompt, and date. Build never regenerates
them; rerunning creates a new dataset version. The measurement-validation module is deferred
(section 19a).

Memory: see section 10.

Language: generated projects have a repository language, English by default. Everything the agent
writes to the repository (docs, journal, decisions, commit messages, issues) uses it, regardless of
the language of the conversation.

Accountability: each section of the paper has an owner who can defend every claim in it. AI
assistance is disclosed through commit trailers and summarized in `docs/ai-use.md`.

## 9. Modules

| Module | Adds |
|---|---|
| collaboration | CODEOWNERS from `reviews`, meeting notes flow (`meetings/raw/`, gitignored by default, + committed distilled notes), issue-only discussion rule |

Other modules (licensed data, human subjects, LLM measurement, timestamped analysis plan,
specifications, ML experiments) are deferred (section 19a).

## 9a. Collaborators without GitHub

Many co-authors work only in Word and email. The `reader` role covers them. In v0, delivery to
readers is manual: a repo member sends the rendered docx or PDF through a channel the project has
approved, and applies the reader's comments to the source by hand. Readers never need a GitHub
account.

## 10. Memory protocol

**Write-back.** Handoff is proposed by the agent, not remembered by the user. Two layers in v0:

1. By rule (AGENTS.md): the agent proposes and performs handoff at natural boundaries: an issue is
   done, the user changes topic, the user signals the end of a session, or context is getting
   heavy (before compaction where the agent makes that visible). This is guidance; agents may not
   follow it reliably. Handoff can also be invoked manually.
2. By recovery, for every agent: at session start the agent checks for commits or uncommitted
   changes not covered by a journal entry, and if it finds a missed handoff, drafts the entry from
   the git history and asks the user to confirm. Recovery is best effort: git cannot reconstruct
   conclusions that were only discussed and never written down.

Automatic handoff hooks are deferred (section 19a).

Handoff writes a journal entry, new decisions, issues for unfinished work, and an AI-use record,
then pushes. Conclusions reached outside the repo (chat apps, email, meetings) are recorded in the
repo.

**Fewer conflicts by structure.** Nothing shared is a single append-only file. Each journal entry is
its own file, one per session, named with a unique session identifier; each decision is its own
file in `docs/decisions/` (dated slug plus a unique identifier, ADR style), superseded by a new file
rather than edited; analysis outputs write one variables file per notebook, merged by build. This
reduces conflicts between parallel branches on memory files; it does not eliminate them. Concurrent
same-person, same-day sessions are a test case. Exact filename formats are defined in the normative
appendix.

**Keeping memory small.** The working estimate, to be measured in the pilots, is that for a
one-year project all history except meeting transcripts totals well under 100k tokens, and what
an agent loads at session start (AGENTS.md, status, brief, recent journal) is under 10k. On that
estimate v0 needs only two rules: meeting transcripts are never loaded whole (search them), and
`docs/status.md` has a size cap enforced by check. Only the
lead edits `docs/status.md`; the distilled note is the record of a meeting.

Deferred until a project shows bloat (multi-year work, large teams, or tools reading across many
projects): tiered hot/warm/cold loading, a generated decision index, and periodic compression of old
journal entries into summaries.

## 11. Agent skills and supported agents

Tested in v0: Claude Code and Codex. pi is best-effort: supported where it works, not a release
gate. Any other agent that reads AGENTS.md and the Agent Skills format (a folder with a `SKILL.md`)
may work but is not tested.

Recurring procedures are written once as Agent Skills in `.agents/skills/` and made available to
each supported agent. A per-agent compatibility table records, for each agent: instruction-file
discovery, skill discovery location, invocation syntax, whether skills are read in place or copied
(and how copies are refreshed without overwriting user edits), tested version, and last
verification date. Entries are verified during implementation, not assumed.

| Skill | Scope | Purpose |
|---|---|---|
| handoff | core | end-of-session write-back |
| consolidate | core | merge journal into status |
| reviewer | core | critique a file as the configured persona; numbered concerns with severity; no rewriting; a different model family than the author model when available; invoked manually |
| meeting-notes | collaboration | transcript (and platform summary) to distilled note; action items to issues after confirmation |
| add-paper | core | DOI metadata to an entry in the project bibliography, empty notes file; no full-text retrieval |

Extension: users add capabilities by dropping any Agent Skill (their own or third-party, for
example writing or figure skills) into the skills folder. There is no plugin system.

## 12. Visibility

**Open:** the working repo is public from day one. Pre-commit checks are mandatory.

**Closed:** the working repo stays private permanently. Any public release of a closed project is
prepared manually by the owner.

In both: never switch a working repo from private to public (history, issues, and PR comments
would be exposed). Open requires the consent of every team member.

Material that may not belong in the repository (meeting transcripts, people-related notes,
pointers to non-public data) is gitignored by default. The README gives guidance on the options
(commit, keep local, or hold in a private repository the project sets up itself), and each project
adjusts these defaults to its own privacy needs and visibility. In an open project, journal entries
are public as well; the README says so, and the project may gitignore `journal/`, in which case
session-start recovery works only on the machine that holds the journal. v0 does not provision a
companion repository.

Releases: CI produces preview artifacts of the rendered paper; these are mutable working drafts,
not citable. Milestone releases (a named, permanent snapshot, such as the submitted version) are
git tags created manually by the owner after review. Archival of a milestone (for example, deposit
with a DOI) is manual in v0.

## 13. Data governance

Every dataset in the data README has a sensitivity tier: public, licensed, confidential
(identifiable people), restricted (contract or ethics board forbids sharing).

v0 accepts only public, synthetic, or owner-approved derived inputs. Confidential and restricted
data do not enter a v0 project. Where a project works with such data upstream, isolating it is the
operator's responsibility; the template provides guidance only and does not verify isolation.

- Tiers and licenses are declared separately for each dataset, and their constraints are
  cumulative: where rules differ on storage, processing, or release, the most restrictive applies.
- Storage: small approved derived data in git; large data in the configured store. Data in the
  licensed, confidential, and restricted tiers is never committed; the declared-paths check
  enforces this for declared datasets.
- Isolation guidance: keeping data outside the working tree, or processing it outside an agent
  session, does not make it inaccessible to an agent running with the same filesystem permissions.
  Effective isolation needs a separately provisioned environment with no access to the sensitive
  data. Agent-specific read-deny settings are an added layer where available, never a guarantee.
- De-identification guidance (recommended practice, not provided as tooling in v0): remove direct
  identifiers; replace IDs with keyed hashes whose key lives outside the repo; coarsen
  quasi-identifiers (age bands, broader geography, shifted or coarsened dates); scrub names and
  contact details from free text with a PII detector run locally (for example Microsoft Presidio)
  plus manual spot checks; check small cells before release; keep any re-identification key
  separate from the data.
- Model boundary guidance: sensitive data only to approved endpoints (institutional gateway with
  no-retention terms, or local models).
- Configured checks: declared dataset paths, forbidden file types, file size limits, and named
  secret patterns. These checks report "configured checks passed", not "no sensitive data exists":
  file contents do not reliably reveal sensitivity or provenance, and pattern scanners do not
  recognize every secret. Committed outputs, rendered documents, and logs (if the project chooses to
  commit them) are release decisions reviewed by the owner.
- PII pattern scan: runs as a warning. It flags likely personal identifiers (for example, email
  addresses and phone numbers) for review, does not block commits, and does not claim to find all
  of them.
- Data openness is per dataset: raw, derived, identifiers-only (others rebuild with their own
  license), synthetic plus access instructions, or availability statement only.

## 14. Paper and replication

- Quarto renders the paper and does not execute code. Analysis writes `_variables.yml`, table files,
  and figures; approved outputs are committed so the paper renders without data.
- A crosswalk from every reported number, table, and figure to its producing script is generated
  from a provenance manifest written alongside these outputs (format defined in the normative
  appendix).
- Variable consistency check: variables produced but never used in the paper, and variables used
  in the paper but no longer produced, are both reported.
- Reference resolution and claim support are separate. Checks mechanically verify that every
  variable reference, table, figure, and citation key resolves. Whether a claim is supported by the
  evidence it references is a human-reviewed assessment: a claim can point to a valid output or
  citation and still be unsupported or overstated.
- Claim audit: at milestones, or on request, an agent with fresh context (a different model family
  when available) lists each empirical claim in the paper and pairs it with the evidence it
  references. Each audit record contains the claim location, the evidence reference, the agent's
  assessment (supported, unsupported, or overstated), and a reviewer disposition recorded by a
  human. Agent assessments are leads for triage, not verdicts.
- Human-drafted sections (`writing.human_drafted`): agents may produce critique-only reports on
  them and may not edit them; edits to these sections are applied by a human. This is enforced by
  instruction and review, not by tooling; the template cannot certify compliance across agents.
- The build entry point (section 14a) doubles as the replication entry point.
- Outputs: a non-empty subset of docx (styled by a reference document) and PDF via Typst, defaulting
  to both; no LaTeX installation needed.
- Replication features provided: single entry point, per-script logs (written locally, not
  committed by default), recorded environment, data availability statement, crosswalk.
- CI in a generated project renders the paper from committed outputs and runs the checks; it does
  not run `prepare` or `analyze`, because those may need data CI does not have. On success it
  updates the preview artifacts (section 12). A failed render or check does not update them.

## 14a. The build entry point

`build.py`, run as `uv run build.py <stage>`, regenerates everything downstream of the data already
in place. Its purpose is everyday consistency during research: after any change upstream, one
command brings every number, table, figure, and the paper back in line. It is also what agents run
to check their own changes. CI runs only the `paper` and `check` stages (section 14). A replication
package at submission is a side benefit.

Stages, runnable together or one at a time:

| Command | Does |
|---|---|
| `uv run build.py all` | all stages below, in order |
| `uv run build.py prepare` | raw or cached inputs to analysis-ready data |
| `uv run build.py analyze` | runs notebooks headless; writes `_variables.yml`, tables, figures |
| `uv run build.py paper` | renders the paper in all configured formats |
| `uv run build.py check` | citation, number, data-exposure, and output checks |

Out of scope for build, each deliberately a separate, explicit step:

- acquiring data (downloads, API pulls, scraping): needs network, credentials, or licenses;
- LLM or other paid API jobs: cost money; build reads their cached outputs and, if an output is
  missing, stops and names the script to run;
- environment setup (`uv sync`), git operations, releases, and publishing.

v0 has no dependency tracking: a stage reruns fully. Expensive work is protected by living outside
build, not by caching inside it. Ordering, prerequisite, failure, and output-freshness rules are
defined in the normative appendix.

## 15. Security for open repositories

Anyone can write issues and comments on a public repo, and agents read them. AGENTS.md instructs
agents to treat content from non-collaborators as data, never instructions; this is guidance that
agents may not follow reliably. Interaction limits can be used as a temporary moderation control,
not as an access boundary. No workflow that invokes an agent runs on pull requests from outside
contributors.

Research data is also an injection channel. Scraped or collected text (transcripts, reviews,
posts, open-ended responses) may contain text written to steer a model. The following measures
reduce this risk; they do not eliminate it. Corpora are processed in bulk by scripts calling model
APIs without tools. Model outputs are validated against a schema, treated as inert data, and never
used as executable commands or file paths. Agents inspect only samples, treat them as data, and do
not run with automatic approval while reading corpora. Residual risk: a manipulated output that
passes schema validation can still be wrong, and repository instructions cannot uniformly control
how every agent handles hostile content.

## 16. Acceptance criteria for a generated project

Acceptance has three groups. Each check reports pass, fail, or not-tested; a check whose
prerequisites are missing (for example, credentials or an agent session) reports not-tested, never
pass.

Local checks (a script, not an agent self-report):

- Environment syncs from a fresh clone.
- Template notebook writes a variable, a table, and a figure; paper renders in every configured
  format with numbered sections, a working cross-reference, and the variable value.
- Configured checks passed: no files at declared raw or non-public dataset paths, no forbidden file
  types, no files over the size limit, and no matches for the named secret patterns are tracked.
  This does not establish that no sensitive data exists; the owner's release review does that.
- The PII pattern scan runs and reports its warnings; warnings do not fail acceptance.
- No CLAUDE.md unless the documented exception.
- Template commit hash recorded as the first decision in `docs/decisions/`.

Agent smoke checks (run per tested agent):

- Session start confirms AGENTS.md loaded.
- Handoff produces a journal entry, and a decision entry when given a decision to record.

GitHub integration checks (require an authenticated remote):

- Push to main runs CI, which renders the paper and runs the checks.
- A successful CI run updates the preview artifacts.

## 17. Template maintenance

- This repo has its own CI: for each fixture answers file (covering solo/team, open/closed, and
  main module combinations), generate a project with the setup script, run the full build on
  synthetic data (all stages), run the local acceptance checks, and run the public-content scan.
- The public-content scan bans private identities (personal names, emails, institutions) and
  non-synthetic research examples in template content, fixtures, and examples. Required attribution,
  license notices, citation metadata, and names of public tools and projects are permitted. The
  scanner's scope and fixtures are defined with it; it catches listed patterns and cannot identify
  every real name, so review remains necessary.
- Template files live under a dedicated directory and are named so agents working on this repo do
  not mistake them for live instructions. The root AGENTS.md of this repo is for maintaining the
  template only.
- Every assumption about external tool behavior (agent instruction files, skill locations, minimum
  versions, Quarto version) is listed in one compatibility file. Assumptions that can be checked
  without an agent session run in this repo's CI on a schedule, so drift is caught before users hit
  it. Agent behavior is checked by running the agent smoke checks manually before each release; the
  result (agent version, date, pass or fail) is recorded in the per-agent compatibility table.
- Versions are git tags with a CHANGELOG entry. v0 promises documented manual migration: each
  release that changes template files includes migration notes that a project owner (or their
  agent) follows by hand. Automated updates are deferred (section 19a).
- Feedback arrives through each project's `docs/workflow-retro.md`.

## 17a. Open-source hygiene for this repository

- Licensing: this repository's own code under MIT; template files (everything under `template/`,
  copied into generated projects) under MIT-0, stating that generated projects belong entirely to
  their users with no attribution required. Third-party files copied in keep their original license
  notice and source; MIT-0 does not remove their obligations. Each generated project chooses its own
  license.
- Required files: LICENSE, README (what it is, status, quick start, non-goals), CITATION.cff,
  CHANGELOG. Also CONTRIBUTING (feedback via issues; PR policy), SECURITY (how to report problems,
  relevant given the data-privacy features), and issue templates for bugs, feature requests, and
  pilot feedback.
- Commits use a no-reply email address. Secret scanning and push protection are enabled.
- Template contents and examples contain no private identities and no non-synthetic research
  examples; required attribution and names of public tools and projects are permitted. Examples use
  synthetic data. CI checks this within the scanner's limits (section 17).
- Public from day 0, developed in the open. The README carries a status banner (pre-release,
  design in progress, breaking changes expected) and versions stay at 0.x until the pilots finish.
- Design documents state decisions with their scope and reason (for example, "no Stata support
  because v0 does not provision or test proprietary runtimes"), not value judgments. Prior-art
  notes say what was borrowed, not how other projects compare. Unsettled questions live in issues
  labeled `open-question`. Pilot details and private reasoning stay in the maintainer's private notes.

## 18. Pilot and success measures

v0 is piloted on several real projects in parallel for several months, covering at least one solo
and one team project, and both open and closed visibility. Solo and team pilots are compared
descriptively; they do not establish a causal effect of the template. Measures:

- setup completes and passes acceptance on the first attempt, and time taken;
- share of work sessions ending with `/handoff`;
- problems caught by checks (quotes, citations, typed numbers, data exposure);
- number and type of retro entries;
- whether documented manual migrations can be followed without errors.

After the pilot, decide what is core, what is a module, and what to remove.

v0 should not be over-engineered in anticipation: build what the pilots use, fix what hurts. The
limit of this approach is that a few pilots show whether it works for their owners, not for others;
wider evidence comes only from outside users (section 19b).

## 18b. Project closure

Every project ends with a closure record in `docs/closure.md`: outcome (published, preprint, blog
post or data app, merged into another project, parked, or abandoned), where it went, and for parked
or abandoned projects, why. Published or released projects get a final tagged release, and the repo
is then archived; both are manual steps in v0. Closure records make outcomes queryable for any
upstream planning tool. Finding an outlet for a finished project is a possible later skill.

## 19. Open questions

- R support as a per-project language choice (environment via rig and renv), using the same
  output contract. Mixing languages within one project stays out of scope.
- Default reference manager for new projects, beyond the single committed bibliography file.
- Availability of a second model family for the reviewer command.
- Default license choices offered to generated projects.

## 19a. Later (not in v0)

Deferred items. None of these are v0 requirements; each needs its own specification before it is
built.

- Private companion repositories for open projects, and routing of non-public material into them.
- Automated export of a closed project into a public repository.
- Account-free delivery to readers without GitHub (for example, public release links).
- Automated archival of milestone releases (Zenodo integration).
- Automatic handoff hooks (session-end or pre-compaction).
- Scheduled, credentialed agent runs in CI for the agent smoke checks.
- A setup question for routing non-public material (commit, keep local, or private repository).
- Word comment transfer from docx back into the source.
- Automated isolation, de-identification tooling, and endpoint governance for sensitive data; the
  licensed-data and human-subjects modules.
- The LLM-measurement module: versioned prompts, codebook, gold set, and an evaluation protocol for
  human agreement.
- The timestamped analysis plan module: a plan snapshot recorded before analysis, with owner
  attestation, an optional external registration reference, the frozen commit, and deviations. It
  cannot by itself establish that outcomes were unseen.
- The specifications and ML-experiments modules; the weekly digest and scheduled agent reviewers.
- Zotero synchronization and full-text PDF retrieval.
- Automated template updates (Copier or a three-way merge); v0 promises documented manual migration.
- Adoption mode: adding the template's layers to an existing project without moving its files.
- Windows support.
- Additional output formats (html) and languages (R, section 19).
- A devcontainer, and a website offering one-click repository creation through a GitHub App.

The notes below record design thinking for two deferred items. They are not requirements.

**Adoption mode.** Most researchers have projects in progress. Adoption mode would add layers
without moving existing files:

1. Inventory: the agent reads the repo and drafts a map of data, scripts, outputs, and the paper,
   plus a draft brief and data README, for the owner to confirm.
2. Memory from now on: status, decisions, journal, and a one-time history summary. Past decisions
   are not reconstructed in detail.
3. Wrap, don't rewrite: build calls the existing scripts in their existing order. Stages that use
   runtimes the template does not test (for example Stata) are marked unverified in build and check.
4. Converge gradually: the output contract (variables, tables, figures) is introduced piece by piece
   as parts of the paper are revised, not all at once.

Setup is safe to rerun and detects existing files, so adoption mode and new-project mode could share
one flow. Adoption mode is the first candidate after v0, ahead of the website.

**Website.** A public site with a button that creates the repository in the user's own GitHub
account:

1. User signs in with GitHub through a GitHub App with minimal, fine-grained permissions.
2. A short form: repository name, public or private, and a project preset (solo project, team
   project) that sets module defaults. Advanced options are collapsed by default.
   Collaborators are added later through GitHub's own invitations.
3. The site creates the repository from this template (marked as a GitHub template) and commits the
   answers as a configuration file.
4. A first-run workflow in the new repository reads the configuration, removes disabled modules,
   fills placeholders, runs the local acceptance checks, and opens the first issue with the results
   as a checklist.

A devcontainer lets the new repository open in Codespaces with everything installed. The site's
backend is limited to sign-in and repository creation.

## 19b. Adoption loop

The goal is usefulness, not marketing, but without outside users the template's effect on others is
unknown. Low-effort channels that follow from normal work: open projects built with the template
link back to it and serve as live examples; short write-ups of what worked and failed in the
pilots; listings in curated resources on AI in economic and business research; a feedback issue
template in every generated repo that points to the starter.

## 20. Prior art this design borrows from

- research-agents: interview-style, idempotent initialization; evidence before prose.
- claude-code-my-workflow: replication protocols; fresh-context verification.
- ml-project-repo-agent-native-template: runnable governance validators; agent techniques drift and
  need retesting.
- Reproducible Generative Research template: paired human and agent documentation.
- Agent-Native Research Artifact: capturing research events at session boundaries.
- Horiuchi's Replication Package Guide: single entry point, crosswalk, per-script logs.
- open-research-data-template: Codespaces-based onboarding.
