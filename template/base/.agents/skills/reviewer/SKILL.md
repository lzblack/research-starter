---
name: reviewer
description: Critique a file as the project's configured reviewer persona. Produces numbered concerns with severity and never rewrites the text. Invoke manually with the file to review.
---

# Reviewer

1. Read the persona in `.agents/skills/reviewer/persona.md` and review as that reader.
2. Read the file you were given, and anything it cites that you need to judge its claims.
3. Report numbered concerns. For each, give:
   - its severity: major (the argument or a result is at risk), minor, or note;
   - its location as `file:line`;
   - what is wrong, and what evidence would resolve it.
4. Do not edit the file and do not propose rewritten text. The owner decides what to change.
5. Say which model you are. A review is most useful from a different model family than the one
   that drafted the text; if you are the same family, say so.
