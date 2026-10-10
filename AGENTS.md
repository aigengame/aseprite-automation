## Primary

Read @RULES.md if exists, to align communication style, collaboration specification, as well as other matters.

## Environment variable names

Name every environment variable defined by SPA with the `SPA_` prefix. Preserve
the names of variables defined by Aseprite, the operating system, or external tools
when integrating with them; for example, `ASEPRITE_USER_FOLDER` and `PATH`.

## README translations

English `README.md` is authoritative. When editing it, review and update every
`docs/README.<locale>.md` in the same change. Translate naturally for each locale,
then refresh and check the source hash as described in
[the translation sync guide](docs/testing.md#readme-translations).

## Agent skills

### State and pitfalls

Read @STATE.md and @PITFALLS.md if they exist.

### Issue tracker

Issues and PRDs are tracked in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Triage uses the five canonical role labels. See `docs/agents/triage-labels.md`.

### Domain docs

This repository uses a single-context layout. See `docs/agents/domain.md`.
