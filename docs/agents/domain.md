# Domain docs

This repository uses a single-context layout.

## Consumer rules

Before architecture, diagnosis, or test-design work:

1. Read `CONTEXT.md` at the repository root if it exists.
2. Read `ARCHITECTURE.md` for the integrated current system view if it exists.
3. Read relevant ADRs under `docs/adr/` if that directory exists.
4. Use the domain terms defined in `CONTEXT.md`. Do not replace them with synonyms that the glossary excludes.
5. Surface any conflict with an existing ADR instead of silently overriding it.

If a context document or ADR directory does not exist, continue without creating an empty placeholder. Create domain documentation only when the project has knowledge or a decision to record.

## Layout

```text
<repository-root>/
├── ARCHITECTURE.md
├── CONTEXT.md
├── docs/
│   └── adr/
└── ...
```
