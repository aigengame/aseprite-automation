# Releases

SPA uses a reviewed Release PR and an exact-commit automatic release workflow.
It publishes one verified Python wheel and source distribution to PyPI, then attaches
the same files to the GitHub Release. Aseprite is supplied separately.

The first PyPI upload starts with a new reviewed Release after this implementation
and its MIT declaration reach `main`. Release-please selects the version. Historical
versions are not backfilled; the existing `v0.3.0` GitHub draft is not reused for newer
code. Until that first upload passes, local package checks demonstrate readiness,
not a completed PyPI release. [Issue #189](https://github.com/aigengame/aseprite-automation/issues/189)
tracks the initial setup and production installation evidence.

## Release authorities

- `pyproject.toml` owns the package description and keywords. Its `readme` field
  selects `README.md` as the package's long description. The build backend projects
  these fields into wheel and sdist metadata for PyPI; no separate PyPI copy exists.
  GitHub About and Topics mirror the project description and keywords. When editing
  those fields, synchronize the repository settings from the same values.
- `release-please-config.json` defines versioning, changelog sections, and tag shape;
  `.release-please-manifest.json` is its released-version ledger.
- `.github/actions/maintain-release-pr/action.yml` projects the selected version into
  the generated `uv.lock` by running `uv lock` on the Release PR branch.
- The Release PR owns the coordinated `pyproject.toml`, manifest, `uv.lock`, and
  `CHANGELOG.md` change.
- `.github/workflows/release.yml` verifies and publishes one exact commit. It never
  chooses or edits a version.

The `Release` workflow runs on pushes to `main`. On an ordinary push, release-please
creates or updates the reviewable Release PR, refreshes its lockfile, and explicitly
dispatches routine CI for the resulting head. Review the complete change and its
three routine jobs, then run [pre-merge Native E2E](testing.md#native-e2e-before-merge)
for its current merge result. Maintenance does not dispatch the costly native suite
on each generated PR update.

After lockfile maintenance, the action waits for the PR API to report the local
Release PR commit before dispatch. It makes at most ten reads, two seconds apart,
and reports expected and observed SHAs on a mismatch. A persistent mismatch fails
maintenance without dispatch; a GitHub CLI error also fails the job. The action's
shell step owns this check and dispatch directly.

Merging the Release PR is the publication approval. Its `main` push makes
release-please create a draft for the reviewed version. The workflow verifies the
draft's exact commit, builds the distributions once, publishes them to PyPI, and
then publishes the GitHub Release with those same files. It maintains the next
Release PR only after the tag exists. This
prevents a tagless draft from regenerating old release history.

## Verification environments

Local real-runtime evidence normally uses the installed macOS Aseprite application.
CI and release verification use Linux and restore the manually prepared binary from
the official source version pinned in `.github/actions/aseprite-runtime/action.yml`,
with scripting enabled and the non-graphical backend. The Linux gate requires
`DISPLAY` and `WAYLAND_DISPLAY` to be absent, exercises the real `--batch --script`
probe, and rejects zero or all-skipped E2E execution.
Release verification selects `e2e and not slow` at the exact release SHA. It retains
the real native suite and small wizard probes; complete example rebuilds are local
opt-in checks. A routine CI or weekly result cannot replace release verification.

Verification uses the shared native shard runner and one final aggregate gate at
the exact release SHA. Source quality, fast tests, metadata, and distribution checks
run alongside the native shards; the aggregate requires all of them to succeed.
Native E2E and Release share resource configuration and the **40-minute allocation**
documented in [verification time limits](testing.md#verification-time-limits), including
preparation, setup, tests, uploads, and aggregation. They do not compile Aseprite
or subtract time. A missing or invalid binary fails the gate and prevents publication.
Run the separate **Build Aseprite** workflow as described in
[manual Aseprite recovery](testing.md#restore-the-aseprite-runtime), then
re-run the original failed Release run to preserve its exact SHA and release tail.
A maintenance success does not authorize publication. Draft creation and publication
remain separate from the verification allocation.

The [issue #107 capacity measurements](evidence/issue-107-ci-capacity.md) retain
historical experiments separately from the current cache-only verification policy.

These results answer different platform questions. Linux headless success does not
cover the macOS bundle or restricted-agent launch path. Neither environment currently
claims windowed Aseprite coverage. See [the test suite guide](testing.md) for the exact
commands and skip policy.

## Configure the first PyPI publisher

### Reconcile the pending GitHub release

Before expecting a new Release PR, resolve the pending pre-PyPI release with the
owner. On 2026-10-07, `main` recorded version `0.3.0`, but its GitHub draft had no
`v0.3.0` tag. The existing maintenance gate therefore returned `ready=false`.
Merging this implementation or running manual verification does not clear that gate.

The original draft belongs to commit
`4db66c94cdb13c68780fdaa42e9666010bd33e3e` and
[Release run 37270734204](https://github.com/aigengame/aseprite-automation/actions/runs/37270734204).
Its package build passed, but native verification failed on a process timeout.
Completing that original GitHub-only run is a possible recovery path, subject to
the owner's decision in #189 and successful verification of its original SHA and
preserved files. Do not bypass the tag gate or attach new code to the old version.
If the owner abandons the draft instead, agree on the release-ledger reconciliation
before creating the next Release PR. Then let release-please select the new version.

### Configure account access

Use the PyPI account that maintains `gda`. Before the first upload, add a
[pending Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
with these exact fields:

| Field | Value |
| --- | --- |
| PyPI project name | `aseprite-automation` |
| GitHub owner | `aigengame` |
| GitHub repository | `aseprite-automation` |
| Workflow filename | `release.yml` |
| GitHub Environment | `pypi` |

Keep the GitHub `pypi` Environment restricted to the `main` branch. It has no
additional reviewer gate: merging the reviewed Release PR is the publication
approval. A pending publisher does not reserve the project name. Verify the
non-secret binding in the owner's PyPI account before the first upload; do not
record passwords or tokens. A successful first upload creates the project and
converts the pending publisher into its publisher. Inspect the project and files
afterward, as required by #189.

### Inspect the public files

Before that first release, inspect the wheel/sdist inventory and public metadata,
including the MIT license and `Copyright (c) 2026 aigengame`. After publication,
install the exact published version in a clean environment outside the checkout,
run the installed-CLI tracer with a separately supplied Aseprite, and verify the
`mcp` extra. Record the SHA, file digests, index version, tested host/runtime and
results in #189. [Issue #54 evidence](evidence/issue-54-installed-distributions.md)
provides the shared installed-wheel checks; it does not substitute for a real
PyPI installation or the release SHA's Linux verification.

The MIT grant covers SPA-owned material. [Third-party notices](../THIRD_PARTY_NOTICES.md)
identify the CC0 Display P3 replacement and its distributed legal text. Package license
metadata comes from `pyproject.toml`; it covers both MIT and CC0 material. The content
verifier checks those declared license files and refuses the known old Apple ICC
payload, including uncompressed embedded copies, in actual wheel/sdist members.
Exact source inventory checks also reject extra packaged files; this is not a general
scanner for every embedded encoding.

[#194 evidence](evidence/issue-194-redistributable-profile.md) records replacement
validation and the owner's historical-copy disposition. The subsequent licensing
check did not establish infringement; the owner accepted retaining historical
copies without making history rewriting or artifact deletion a public-readiness
requirement. Current source and new packages use the CC0 reference. Reassess that
disposition if concrete contrary licensing evidence or a rights-holder request
appears. #189's first-publish inspection must use newly built distributions containing
the replacement; old artifacts cannot be relabeled as the corrected output.

## Prepare and publish a release

1. Merge ordinary changes after routine CI, review and current-merge Native E2E pass.
2. Review the Release PR. Confirm that its version, changelog, manifest, project
   metadata, and lockfile agree, its routine CI passes, and pre-merge Native E2E
   passed for the current base/head/merge target.
3. Before the first public release, select the Release PR branch on the Actions page
   and manually run `Release`. A manual run is verification-only: it exercises source
   checks, fast tests, the Linux real Aseprite E2E gate, package build, metadata checks,
   and the installed-wheel smoke test without creating a draft, tag, or release.
4. Merge the Release PR. The resulting `main` push creates the draft and reports its
   exact commit. All read-only verification jobs check out that commit. The quality
   job validates the reviewed release metadata and builds the wheel and sdist once;
   each native shard also prepares an isolated wheel installation for its CLI tests.
   The final aggregate requires every quality gate and every selected native case.
   The PyPI job downloads those artifacts, checks any existing index files against
   their version, size and SHA-256, and uploads the missing files with Trusted
   Publishing. It then requires both files to match on PyPI before the GitHub job
   attaches the same artifacts and publishes the draft.

The publisher depends on successful verification of the draft's reported SHA. A
generally green branch or a successful job for a different commit is never accepted as
release evidence.

## Permissions and artifacts

The verification jobs have read-only repository permission. They run project code,
native Aseprite, tests, and the build backend. The quality job stores the exact-SHA
distributions as a run-scoped artifact, and the aggregate audits the native reports.
The draft-cutting job has only repository release and pull request permissions and
runs no checked-out project code. Only the PyPI upload job has `id-token: write`,
scoped by the `pypi` Environment and Trusted Publisher binding. It checks out only
the reviewed stdlib release-file verifier, which reads archives as data. It does not
install SPA, import its package code, run tests, or invoke the build backend.
The PyPA action exchanges the job's OIDC identity for short-lived upload authority;
no long-lived PyPI token is stored in the repository.
It receives a copy of the preserved distribution pair in its own upload directory,
where it can generate attestations. The post-upload check still reads the original
pair, and GitHub receives the preserved artifact; attestation sidecars do not become
extra distribution files or weaken the two-file check.

The GitHub publisher has repository contents permission for the existing draft and
read access to the verified run artifact. It downloads that artifact, attaches exactly
one wheel and one sdist, and publishes the draft only after the PyPI job succeeds.
A separate post-release job owns the permissions needed to maintain the next Release
PR and dispatch its CI. Verification-only manual runs never upload to either destination.

The public-content check requires the declared license metadata and files, the packaged Python
and Kernel files, and the expected build metadata. It rejects duplicate member names,
extra archive contents, unresolved LFS pointers and unexpected distribution files.
It does not package the Aseprite program, runtime caches, examples or workspace
configuration. Publishing a wheel and sdist makes their contents public even while
the GitHub repository is private.
Repository visibility and Aseprite binary-cache compliance remain with
[issue #126](https://github.com/aigengame/aseprite-automation/issues/126).

A draft/tag can already exist when verification fails. No PyPI upload or public
GitHub Release follows failed source checks, tests, Linux real Aseprite E2E, metadata
validation, package checks, or installed CLI verification.

## Recovery

- When a manual non-publishing verification fails, fix the Release PR branch and run
  the verification again on its new head.
- When Release PR maintenance fails after release-please creates or updates the PR,
  use **Re-run failed jobs**. The maintenance action resolves the existing open
  Release PR, regenerates and validates its lockfile, verifies its remote head, and
  dispatches exact-head CI even when release-please has no new PR update to report.
- When verification fails after a draft was cut, use **Re-run failed jobs** after the
  cause is corrected without changing the reviewed release commit. The publisher is
  deliberately marked failed too, so failed shards/quality checks, aggregation, and
  publication resume while the successful draft job remains fixed. The aggregate
  still requires a complete set of reports for the same target and configuration.
- When draft creation fails before a release exists, use **Re-run failed jobs** after a
  transient GitHub failure.
- When PyPI setup, OIDC exchange or upload fails, correct the setup and use
  **Re-run failed jobs**. A matching partial upload can resume: existing filenames
  are accepted only when the reviewed version, file size and SHA-256 match the
  preserved artifacts. `skip-existing` alone is not proof of a match. Conflicts fail
  explicitly; investigate instead of replacing files or silently bumping the version.
- When PyPI succeeds but GitHub upload or draft publication fails, the PyPI files
  are already public. Use **Re-run failed jobs** to resume GitHub publication;
  `gh release upload --clobber` reuses the same two artifacts. This is recovery,
  not rollback of the PyPI upload.
- A PyPI lookup failure, or an upload not yet visible through its JSON API, fails
  the publication tail. Retry failed jobs after the service recovers. The verifier
  requires the complete matching pair before GitHub publication.
- Distribution artifacts are retained for 30 days. Recover within that window.
  If the original files are no longer available, stop and resolve the release with
  the owner; do not rebuild and assume that new bytes belong to an existing version.
- Do not rerun every job after a draft was created. A full rerun can ask
  release-please to cut the same untagged release again. Resume only failed jobs.
