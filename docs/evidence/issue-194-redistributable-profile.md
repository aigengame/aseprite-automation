# Redistributable Display P3 reference — issue #194

## Decision and scope

[#194](https://github.com/aigengame/aseprite-automation/issues/194) replaces the
distributed Apple ICC resource with the CC0 `DisplayP3-v4.icc` from Compact ICC
Profiles. The [packaged notice](../../src/spa/kernel/color/profiles/NOTICE.txt) is
the provenance record: it pins the upstream commit, original path, digest, and
license. [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md) indexes the notice
and distributed CC0 legal text. SPA-owned code and documentation remain MIT.

An admitted input does not need a distributed reference copy. The Color Profile
owner's `identities.json` contains complete-byte hashes and permitted conversion
pairs. Python and Lua hash the actual input. They do not trust the profile name,
claimed digest, or a partial ICC structure. Native conversion still receives the
caller's original bytes and runs only in Aseprite.

- `display_p3_cc0` identifies the new 480-byte reference.
- `display_p3` continues to identify the previously accepted 536-byte Apple input,
  supplied by the caller. SPA does not include, download, or reconstruct it.
- Each P3 identity supports conversion to built-in sRGB and to itself. Conversion
  between these distinct P3 files is refused. Linear-sRGB behavior and valid-ICC
  Assign remain independent and unchanged.

This finite set can expand with accepted demand and native evidence. It is not a
general classifier or a promise that every Display P3 encoding works. See
[ADR-0089](../adr/0089-native-color-operation-boundaries.md) for ownership.

## Feasibility evidence

The pre-implementation prototype used local macOS Aseprite 1.3.18.5, RGB and
Indexed samples, native conversion, save/reopen, and independently decoded PNGs.
Both Apple and CC0 files converted `(180,70,30,127)` to `(195,60,2,127)` in sRGB.
The Palette sample matched, Indexed pixels retained their indexes, and PNGs
preserved the exact selected ICC bytes.

Of 344 RGB samples, 342 matched between Apple and the selected CC0 file; two
differed by at most one 8-bit channel value. The alternative `DisplayP3Compat-v4`
file differed in 53 samples, with a maximum difference of two, and changed the
established sample to `(195,60,4,127)`. It was not selected. These are bounded
observations, not numerical equivalence or whole-gamut certification.

## Implementation validation

Executed on macOS with separately supplied Aseprite 1.3.18.5 and CPython 3.13.13.
The core replacement is commit `6820d8c`; follow-up changes add caller-input
coverage and reconcile documentation. The PR records the final reviewed head.

| Check | Result |
| --- | --- |
| TDD: `plan check` accepts the CC0 target without launching Aseprite | Failed before identity admission; passed after replacement |
| Affected native suite: Color Profile, Preparation, Import, static PNG, Sprite Sheet, Tileset, and animation export | 231 passed in 228.78 seconds |
| Focused follow-up: both P3 identities, same-file conversion, cross-P3 refusal, caller-supplied Preparation/Import/PNG preservation | 22 passed in 34.26 seconds |
| Fast suite, `not e2e` | 1,998 passed; two process-inspection tests were sandbox-blocked and passed on a focused rerun with `ps` access |
| Ruff lint/format; Pyright | Passed; no type errors |
| Luacheck / StyLua over all 284 tracked Lua files | Passed; zero warnings or errors |
| Wheel built from sdist; archive inventory/license verification; Twine | Passed |
| Isolated wheel inventory | SPA 0.3.0 loaded from its own environment; all 145 Kernel resources matched |
| Isolated wheel native tracer: runtime discovery, Plan, PNG export, typed failure | 4 passed in 5.15 seconds |

`tests/color/fixtures/profile_digest.lua` compares Lua SHA-256 with Python's
independent `hashlib` results, including padding/block boundaries and binary input.
Conversion tests compare standalone and live Plan results with independent native
calls and reopened files. Failed directions preserve Source and existing Target.

Normal tests use the CC0 fixture. Set `SPA_TEST_APPLE_P3_ICC` explicitly to run the
optional Apple-input cases. The helper checks the previously admitted complete
digest; it does not locate host files or fetch the file. The follow-up cases use
that input for Preparation, compatible Import, static PNG export, and same-file
conversion. An unset variable skips only these optional cases.

The new reference probe does not establish new cross-runtime evidence for the
Apple file. Linux Native E2E and Release remain suspended under #126, and no Linux
result is claimed here. The known Linux converter Capability Gap is unchanged.

## Current files and distribution check

A one-time scan of 1,261 tracked working-tree files found no old Apple ICC. It
checked complete raw ICC spans, including native Aseprite embedded profile bytes,
and decoded PNG iCCP chunks. The checkout had no matching raw spans or PNG ICC
chunks. This does not describe old commits or arbitrary compressed containers.

The existing distribution verifier inventories every expected source member and
license file from `pyproject.toml`. It rejects the known Apple payload as a direct
or uncompressed embedded ICC in actual wheel/sdist members. It does not implement
a generic encoded-content scanner. The current package has no PNG resource path;
unexpected archive members are rejected. Tests use a synthetic ICC-shaped sentinel
for negative archive checks, not a reconstructed Apple resource.

The candidate wheel and sdist are local validation builds at the existing 0.3.0
development version. They are not an upload, a historical release replacement, or
authorization to publish. A future release still uses its reviewed release version.

## Historical copies: disposition still required

The [read-only inventory](https://github.com/aigengame/aseprite-automation/issues/194#issuecomment-6051655588)
records concrete refs, artifact IDs, run IDs, and coverage limits, as observed at
2026-10-08 03:30 UTC. No history or remote object was deleted.

| Location | Evidence | Next action before public readiness |
| --- | --- | --- |
| Git history and branch tips | Old blob `a484af3025b82a9a9a64e4c6a36acd345856a5f7`; 37 of 40 observed remote heads/tags contained it. Earlier audit also found PR refs. | Merge this source fix; separately authorize and execute a history/ref disposition plan, including GitHub-retained PR objects. Branch-tip replacement alone is insufficient. |
| Actions artifacts | 95 retained containers held 190 direct ICC members in wheels/sdists; one previously identified container was already absent. | Refresh the recorded IDs, then explicitly authorize removal of affected artifacts. Rebuild any still-needed distributions from corrected source. |
| Existing v0.1.0/v0.2.0 Release assets | Four inspected wheel/sdist assets had no direct member matching the old ICC. | No deletion justified by this direct-copy finding; retain the audit's embedded-content coverage limitation. |

The archived-member audit did not decode every embedded PNG/Aseprite profile and
does not establish absence in inaccessible objects or external consumers. The
current-tree check above has a different scope. Recheck affected objects after
authorized cleanup. #126 remains the public-readiness gate; merging #194 alone
does not make the repository ready to become public.
