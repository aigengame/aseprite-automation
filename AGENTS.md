## Primary

Read @RULES.md if exists, to align communication style, collaboration specification, as well as other matters.

Read @CONTEXT.md for the project scope and shared domain language. Use
@ARCHITECTURE.md for the current system view and the relevant records in `docs/adr/`
for architecture decisions and their rationale.

`README.md` is user-facing onboarding (installation, usage, and contributing).
Read the sections relevant to the task; read the full file when the task requires it.

### State and pitfalls

Read @STATE.md and @PITFALLS.md if they exist.

### Environment variable names

Name every environment variable defined by SPA with the `SPA_` prefix. Preserve
the names of variables defined by Aseprite, the operating system, or external tools
when integrating with them; for example, `ASEPRITE_USER_FOLDER` and `PATH`.

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Triage uses the five canonical role labels. See `docs/agents/triage-labels.md`.

### Domain docs

This repository uses a single-context layout. See `docs/agents/domain.md`.
