---
status: accepted
---

# Delegate Agent Skill distribution to the Skills CLI

## Context

[Issue #52](https://github.com/aigengame/aseprite-automation/issues/52) previously planned
a version-locked Agent Skill inside the Python package and a `spa skill` installation
command. The owner accepted separate distribution through the existing Skills CLI.
The official [Skills CLI](https://github.com/vercel-labs/skills) supports discovery at
`skills/<name>/SKILL.md`, installation into supported agents, and native source/update
handling. SPA does not need its own installation or version-management mechanism.

## Decision

The Skill source is `skills/spa/SKILL.md`. Use the Skills CLI's native discovery,
installation, update, and version-management behavior. SPA provides no `spa skill`
command, duplicate Skill asset in its Python wheel, or additional Skill version-management
policy, Skill-to-CLI release coupling, lock format, or registry. Skill installation does not install
SPA or Aseprite. The Skills CLI's Node/npm requirement belongs to that installation
tool; it is not a SPA Python runtime dependency.

The Skill is self-contained and self-describing. Its instructions let the consuming
agent discover the actual installed SPA surface, determine which instructions apply,
and construct supported requests. Use existing discovery, help, schemas, and typed
outcomes for that judgment. If the required capability cannot be established, the
instructions tell the agent to report the missing capability or uncertainty rather
than invent a command or assume success.

This is implicit compatibility through the Skill's own guidance. There is no external
Skill-to-CLI compatibility checker, version-pair matrix, handshake, or certification
service. The guidance does not promise compatibility with every SPA release. Existing
Descriptor validation and native-runtime checks retain their responsibilities under
[ADR-0002](0002-operation-descriptor-authority.md); they do not judge Skill compatibility.
Keep command and parameter authority in the installed surface rather than copying a
second contract catalog into the Skill.

The Skill stays in Access Projection within the current Bounded Context. Further
guidance or installation targets can be added for an accepted consumer need. Such work
must remain proportional under [ADR-0007](0007-demand-driven-nfrs.md), without turning
Skill delivery into an NFR platform.

## Consequences

- #52 owns a discoverable and installable Skill plus a bounded real SPA workflow. Its
  instructions carry the capability checks and failure handling needed for that use.
- [#54](https://github.com/aigengame/aseprite-automation/issues/54) checks Python/Kernel
  installation separately and references the Skill installation/use evidence from #52.
  It does not check for Skill files in the wheel or a Skill/CLI version relationship.
- The accepted mechanism replaces the former package/version coupling in the PRD and
  feature plans. It does not itself deliver the Skill; #52 owns implementation status.
