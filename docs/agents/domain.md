# Domain docs

This repository uses a single-context layout.

## Consumer rules

Before architecture, diagnosis, or test-design work:

1. Read `AUTHORITY_MATRIX.md` for repository artifact ownership and projection rules if it exists.
2. Read `CONTEXT.md` at the repository root if it exists.
3. Read `ARCHITECTURE.md` for the integrated current system view if it exists.
4. Read relevant ADRs under `docs/adr/` if that directory exists.
5. Use the domain terms defined in `CONTEXT.md`. Do not replace them with synonyms that the glossary excludes.
6. Surface any conflict with an existing authority instead of silently overriding it.

If a context document or ADR directory does not exist, continue without creating an empty placeholder. Create domain documentation only when the project has knowledge or a decision to record.

## Layout

```text
<repository-root>/
├── AUTHORITY_MATRIX.md
├── ARCHITECTURE.md
├── CONTEXT.md
├── docs/
│   └── adr/
└── ...
```
