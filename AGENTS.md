# EVIDENT — Codex Development Instructions

## Project
EVIDENT (sp-app) is a SaaS application for sole proprietors in Bosnia and Herzegovina (RS, FBiH, and Brcko District).

Repository root:
`/home/miso/dev/sp-app/sp-app`

Main application areas:
- `frontend/` — React/Vite frontend
- `backend/` — Python backend
- `.github/` — CI workflows

## Core Working Principle
Make the smallest safe change that fully solves the requested task.

Preserve existing behavior unless the task explicitly requires changing it.

Do not perform unrelated refactors, cleanup, formatting, dependency upgrades, architectural changes, or file reorganizations.

Before editing, inspect the relevant existing implementation and understand how the requested area currently works.

## Scope Control
Only modify files required for the current task.

If a requested change appears to require broader changes than expected, stop and explain why before proceeding.

Never silently expand task scope.

Do not change business logic, tax logic, financial calculations, database schema, migrations, authentication, tenant isolation, or API contracts unless explicitly requested.

## Git Safety
Before starting implementation work, inspect:
- current branch
- `git status`

Do not switch branches unless explicitly instructed.

Do not commit, merge, rebase, reset, stash, tag, or push unless explicitly instructed.

Never use destructive Git commands without explicit approval.

Never discard existing user changes.

At the end of each task, report:
- files changed
- concise summary of changes
- checks/tests performed
- `git status`

Show/review the relevant diff before any commit.

## Editing
Prefer targeted, minimal-risk changes.

Maintain the existing coding style, architecture, naming conventions, and patterns already used in the repository.

Do not rewrite complete files unnecessarily when a targeted edit is safer.

Do not modify generated files unless explicitly required.

## Frontend Verification
For frontend changes, run appropriate checks when applicable.

Prefer running the project's already-installed local TypeScript compiler.

`npx tsc --noEmit` may be used only when it resolves to an already-installed project dependency and does not download or install anything.

If the required dependency is unavailable, stop and report it instead of installing or downloading packages.

Also run any task-specific frontend checks or tests that already exist and are relevant.

Do not claim a check passed unless it was actually executed successfully.

## Backend Verification
For backend changes, run the relevant existing tests.

Prefer focused tests first, followed by broader tests when justified by the scope of the change.

Respect the repository's existing pytest configuration and test isolation.

Do not alter tests merely to make failing application behavior appear correct.

## Docker and Database
Do not remove or recreate Docker volumes, databases, containers, or persistent data unless explicitly instructed.

Do not run destructive database commands.

Do not create or apply migrations unless the task explicitly requires a schema change and approval has been given.

Preserve the existing demo/development data unless explicitly instructed otherwise.

## Dependencies and Configuration
Do not install, remove, or upgrade dependencies unless explicitly requested.

Do not modify environment files, secrets, credentials, Docker configuration, CI configuration, or deployment configuration unless required by the task.

Never expose or commit secrets.

## Communication
When requirements are ambiguous and the ambiguity could materially affect implementation, ask before making the change.

For straightforward, low-risk implementation details, inspect the existing code and follow established project patterns.

Clearly distinguish:
- what you observed
- what you changed
- what you tested
- anything that remains uncertain

Never claim that a file, test, command, Git state, or application behavior was inspected or verified unless it actually was.

## Approval Boundary
Repository inspection and normal read-only diagnostics are allowed.

Implementation changes must stay strictly within the user's requested scope.

Commit and push are separate actions and always require explicit instruction.
