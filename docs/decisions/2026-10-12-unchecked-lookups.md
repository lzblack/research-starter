# Unchecked lookups in generated projects

Date: 2026-10-12

## Decision

Generated projects get one always-on agent rule, listed under "Records and untrusted content" in `AGENTS.md`: if the agent did not look something up or run a check, it says so, and never states the result from memory or by guessing. PRD section 8 (Accountability) states the same requirement. The claim audit format, the quotation rule, and the reviewer skill are unchanged, and no check enforces the rule.

## Reason

Existing rules cover invented quotations and hand-typed result numbers, but not other facts an agent can report without checking, such as what a source says or what a dataset covers. Such errors apply to any empirical project and are hard to detect later. The rule is stated by where a result comes from rather than by how likely it seems, so it does not depend on the agent's judgment of plausibility.

## Alternatives considered

- Require agents to grade each statement about evidence as observed, inferred, or checked. Not adopted: it adds a reporting format that not every project needs.
- Use the same grades in claim audits. Not adopted: audits assess whether evidence supports a claim, a different question, and their format is fixed in PRD section 14.
- Add a same-standard-for-all-sources stance to the reviewer skill. Not adopted: projects can state it in their reviewer persona.
- List the rule in PRD section 19a (Later) until the pilots report the problem.

## Decided by

maintainer
