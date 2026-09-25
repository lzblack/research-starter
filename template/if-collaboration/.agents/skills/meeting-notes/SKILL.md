---
name: meeting-notes
description: Turn a meeting transcript or platform summary from meetings/raw/ into a distilled note in meetings/, and propose issues for action items. Use after a meeting.
---

# Meeting notes

1. Read the transcript or summary the user names in `meetings/raw/`. Search it rather than
   loading a long transcript whole. Never commit anything from `meetings/raw/`.
2. Write `meetings/YYYY-MM-DD-<slug>.md`:

   ```markdown
   ---
   date: <YYYY-MM-DD>
   attendees:
     - <names as in project.yml>
   source: transcript
   ---

   ## Decisions
   ## Action items
   ```

   - `source` is `transcript`, `summary`, or `notes`.
   - Keep only what the team needs later: decisions, their reasons, and action items with owners.
     Leave out personal remarks.
3. List the proposed issues (title and owner) and ask the user to confirm them. Then create them
   with `gh issue create` and link each one from its action item.
4. The distilled note is the record of the meeting. Record decisions that change the project
   with the handoff skill.
