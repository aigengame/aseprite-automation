# SPA Agent Skill installation and use

This is bounded delivery evidence for [#52](https://github.com/aigengame/aseprite-automation/issues/52),
recorded on 2026-10-06. It supplies Skill installation/use evidence for
[#54](https://github.com/aigengame/aseprite-automation/issues/54); it does not certify
other agents, operating systems, or SPA versions.

## Tested inputs

- Skill: [`skills/spa/SKILL.md`](../../skills/spa/SKILL.md), source commit
  `89a59c2c0b5f8933804187269731acf0d245675b`.
- Skill file SHA-256: `d57b7abf997387e56290f7cba2d2909e34e30269aa550a5444d987b0f78aeb2f`.
- Skills CLI: 1.7.0; target: Codex, project scope, copy mode.
- SPA: 0.2.0, wheel built from this checkout and installed with locked runtime
  dependencies in a separate Python 3.13.13 environment. No editable install or
  source-tree imports were used for the consumer workflow.
- Host/runtime: macOS 27.0.1 arm64; caller-supplied Aseprite 1.3.18.5-dev,
  scripting API 41, Lua 5.4.

These identifiers record what was tested. They are not a Skill version policy or a
Skill-to-CLI compatibility rule.

## Installation checks

From an isolated consumer directory, use the Skills CLI's native Git source syntax:

```sh
npx skills add 'https://github.com/aigengame/aseprite-automation.git#codex/issue-52-spa-skill' --list
npx skills add 'https://github.com/aigengame/aseprite-automation.git#codex/issue-52-spa-skill' --skill spa --agent codex --copy --yes --json
npx skills list --agent codex --json
```

The feature branch contained the source commit above at the time of testing. A later
replay can select the recorded commit through the Skills CLI's native reference syntax.
Repository access was available through the caller's existing credentials.

Discovery found one Skill, `spa`. Installation returned `status: installed`; listing
reported Codex and project scope. The installed `.agents/skills/spa/SKILL.md` was a
regular file and byte-identical to the source. The consumer directory contained only
that Skill and the Skills CLI's own lock file before the workflow began. No external
Skill-to-CLI checker or SPA-managed installation state was added.

The `skill-creator` `quick_validate.py` check passed. The existing
`scripts/verify_installed_cli.py` check verified SPA 0.2.0 and all 143 packaged Kernel
resources. Wheel inspection found no `SKILL.md` copy.

## Independent forward test

An independent Sol agent received only the installed Skill, installed executable
paths, an isolated consumer directory, and this request: create a 16×16 transparent
RGB sprite with one Frame and a centered 8×8 square in RGBA (32,96,224,255); deliver
the editable sprite and PNG, verify their facts, check repeat-creation protection,
and determine whether the installed SPA can rasterize font text `GO`.
It was not given a solution or repository source, tests, or README access.

| Observation | Actual result |
| --- | --- |
| Discover and author | Used installed help/schemas, `sprite create`, and `paint rectangle`; the square occupies x/y 4–11. Both saves reported persisted reopen verification. |
| Inspect and validate | `sprite get` reported 16×16 RGB with one Frame. `sprite validate` returned `valid: true` and four matching expected facts. |
| Export | `export image` produced a 16×16 RGBA PNG; independently decoded with Pillow. |
| Pixel verification | All 256 pixels matched: 64 exact blue pixels in the square and 192 transparent black pixels outside it. |
| Repeat creation | `overwrite: false` returned `target_commit_failed` with reason `overwrite_not_allowed`; existing file bytes retained the same SHA-256. |
| Missing text capability | `spa info` declared a native text rasterization Capability Gap. The agent reported the limitation and made no text mutation or invented command. This consumed the declared evidence; it did not rerun the historical native text experiments. |
| Independent schema checks | The create, paint, inspect, validate, export, and refused-repeat requests and outcomes all matched the installed request/result/failure schemas. |
| Validation verdict | A separate expected-width-17 check against the 16-pixel asset returned process exit 0 and `status: success`, but `valid: false` and a width Finding. |

The exported PNG was 109 bytes with SHA-256
`4999dc290232ef086e3ba8add5243d2f372a4dd8bc7cf9448759968139166bd6`;
its independently measured size and digest matched the returned Artifact. The
creation-stage source retained SHA-256
`0547be7f8303ff064ed7e2acd11f9e3d9207c983b2ac67c2e5e4e0804b99e7b3`
before and after the refused repeat.

This test demonstrated usable entry guidance and handling of a declared missing
capability and a typed failure. It did not exercise every workflow mentioned by the
Skill or establish visual quality beyond the specified pixel fixture. Full native
E2E and Linux installation validation remain outside this bounded Skill test.
