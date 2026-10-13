# Creating the GitHub repository first

Date: 2026-10-13

## Decision

- A new project may be generated into a clone of a GitHub repository the user just created. The clone may hold only GitHub's initial commit with README.md, LICENSE, or .gitignore. `generate` replaces README.md and .gitignore with the template's files, reports them with the new output verb `replace`, and keeps LICENSE. Any other existing history is still refused, since adoption of existing projects is deferred.
- `provision` treats HTTPS and SSH URLs of the same GitHub repository as the same remote. When the remote has commits the project does not contain, the push step fails with a message naming the two ways to fix it; it never merges or force-pushes.
- The bootstrap preflight also checks the operating system and the GitHub CLI login and scopes. A GitHub problem is reported and a fix offered, but it does not block local generation.
- After the initial commit, the bootstrap agent tells the user that the project exists only locally and asks whether to connect it to GitHub now.

## Reason

Creating the repository on GitHub, often with a README, license, or .gitignore, and then cloning it is a common way to start a project, and setup refused it. The replaced files remain in the repository's history, so replacing them loses nothing. Merging GitHub's initial commit during `provision` would cover the other order as well, but it would add a commit the user did not make; a clear failure message is enough there. Checking the platform and GitHub access first avoids failures after the setup questions. GitHub access stays optional during local generation because PRD section 4 keeps that phase independent of GitHub.

## Alternatives considered

- Documentation only: tell users to create the GitHub repository without initialization files. Not adopted: setup would still fail for the common habit.
- Also merge GitHub's initial commit in `provision` when the project was generated elsewhere.
- Make a missing or unauthenticated GitHub CLI a preflight failure.

## Decided by

maintainer
