# Repository language

Date: 2026-09-24

## Decision

Generated projects have a repository language. A `language` setup question sets it, and the
default is English. Everything the agent writes to the repository (docs, journal, decisions, commit
messages, issues) uses it, whatever language the conversation is in.

## Reason

People often talk to their agent in a language other than their project's. If agent output
followed the conversation, the shared record would mix languages, and collaborators, reviewers, and
later sessions could not rely on reading it.

## Alternatives considered

- Write in the language of the conversation.
- Fix English for all projects with no setup question.

## Decided by

maintainer
