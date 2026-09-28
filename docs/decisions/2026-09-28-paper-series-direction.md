# Direction for paper series (deferred)

Date: 2026-09-28

## Decision

Several papers in one project, and moving a paper into its own repository, are added to the PRD's
Later section, with a minimal design direction:
- The first paper stays in `paper/`, and setup is unchanged.
- Further papers get descriptive directory names, not numbers, and are listed in configuration.
- A series stays in one repository while one person or a stable team works on it.
- A paper moves to its own repository when it needs a different access boundary. It then uses
  shared data through declared dataset versions.

Nothing is built until a pilot produces a paper series.

## Reason

The number of papers is not known when a project starts, so a choice between one repository per
paper and one repository per project cannot be made at setup. Materials are shared best across a
project, while access is granted best per paper, and GitHub grants access per repository. The
direction keeps both options open at no cost to single-paper projects. It adds no paper
identifier, no second layout, and no tooling before a real need. Descriptive names stay valid
when plans for a series change; numbers do not.

## Alternatives considered

- Always one repository per paper, the v0 behavior, which makes a single researcher's series
  duplicate materials across repositories.
- A multi-paper layout (`papers/<id>/`) from the first paper.
- A separate data repository plus paper repositories from the start.
- Numbered paper directories, or a stable internal paper identifier separate from the directory
  name.

## Decided by

maintainer
