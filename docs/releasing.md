# Releases

SPA uses a reviewed Release PR and an exact-commit automatic release workflow.
It publishes one verified Python wheel and source distribution to PyPI, then attaches
the same files to the GitHub Release. Aseprite is supplied separately.

The first PyPI upload starts with a new reviewed Release after this implementation
and its MIT declaration reach `main`. Release-please selects the version. Historical
versions are not backfilled; the withdrawn `v0.3.0` version is not reused for newer
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
  `.release-please-manifest.json` records its version baseline. A version or tag
  alone does not prove publication; check the GitHub Release and PyPI files.
- `.github/actions/maintain-release-pr/action.yml` projects the selected version into
  the generated `uv.lock` by running `uv lock` on the Release PR branch.
- The Release PR owns the coordinated `pyproject.toml`, manifest, `uv.lock`, and
  `CHANGELOG.md` change.
- `.github/workflows/release.yml` verifies and publishes one exact commit. It never
  chooses or edits a version.

The `Release` workflow runs on pushes to `main`. On an ordinary push, release-please
creates or updates the reviewable Release PR, refreshes its lockfile, and explicitly
dispatches routine CI for the resulting head. Review the complete change and its
three routine jobs. Native verification runs only after the reviewed code reaches
main, through the Release admission gate. PR updates cannot schedule the private
Aseprite runners.

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
Release verification uses Linux runners in the restricted `spa-release` group,
with Aseprite privately provisioned on the host. It requires `DISPLAY` and
`WAYLAND_DISPLAY` to be absent, exercises real `--batch --script`, and rejects zero
or all-skipped E2E execution. Routine CI remains GitHub-hosted and does not need
Aseprite. Neither path builds, downloads or caches the Aseprite binary.

The shared reusable workflow admits only this repository's `release.yml` from main,
for push or manual events. Its hosted admission checks the full release SHA against
the current run's Release record and original main event history; manual verification uses the
original event SHA. No caller-supplied target is checked out in admission. Only the
validated target output can reach the private runner. See
[Release runner setup](testing.md#release-runner-setup) for the runner-group access
restriction that must accompany these checks.

Verification selects `e2e and not slow` at the exact release SHA using the same
configurable shard runner as local execution. It keeps small wizard probes and
excludes complete example rebuilds. Quality, fast tests, metadata and distribution
checks run on GitHub-hosted runners; the final hosted gate requires all checks and
complete exact-SHA shard evidence before publication.

The **40-minute verification allocation** includes hosted preparation/admission,
private shard execution and hosted aggregation, as specified in
[verification time limits](testing.md#verification-time-limits). No compilation time
is deducted. A missing runtime fails the gate. Repair it on the host and
[rerun the original failed Release jobs](testing.md#restore-the-aseprite-runtime).
Draft creation and publication remain separate from that verification allocation.

These results answer different platform questions. Linux headless success does not
cover the macOS bundle or restricted-agent launch path. Neither environment currently
claims windowed Aseprite coverage. See [the test suite guide](testing.md) for the exact
commands and skip policy.

## Configure the first PyPI publisher

### Withdrawn pre-PyPI release

On 2026-10-10, the owner authorized reconciliation of the empty `v0.3.0` draft
and its version baseline. The unpublished draft was removed. The annotated
`v0.3.0` tag retains the original reviewed Release PR #111 commit,
`4db66c94cdb13c68780fdaa42e9666010bd33e3e`.
The tag states **withdrawn before publication**: in
[Release run 37270734204](https://github.com/aigengame/aseprite-automation/actions/runs/37270734204),
the package build passed, but native verification failed on a process timeout.
No GitHub Release or PyPI package was published for this version. The tag records
historical source; successful release verification remains unproven for that commit.

At reconciliation, `main` still recorded `0.3.0` in the manifest, project version
and lockfile. Release-please generated
[Release PR #205](https://github.com/aigengame/aseprite-automation/pull/205) for `0.4.0`.
Its
[native tag fallback](https://github.com/googleapis/release-please/blob/v17.3.0/docs/troubleshooting.md#how-does-release-please-determine-the-previous-release)
used the original commit as its comparison boundary without a version override.
At reconciliation, the latest published GitHub release was still `v0.2.0`.
Do not move the withdrawn tag to newer code, restore #111's pending label, or resume
its historical workflow, which uses the retired binary-cache path. The next reviewed
Release follows the current verification and publication workflow.

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

1. Merge ordinary changes after review and routine CI.
2. Review the Release PR. Confirm that its version, changelog, manifest, project
   metadata and lockfile agree and its routine CI passes.
3. To verify main without publishing, select **main** in **Actions → Release → Run
   workflow**. A manual run checks that event's exact commit, including the native
   suite and wheel installation, without creating a draft or publishing. Dispatches
   from PR branches or dev are rejected.
4. Merge the Release PR. The resulting `main` push creates the draft and reports its
   exact commit. All read-only verification jobs test that commit. The quality
   job validates the reviewed release metadata and builds the wheel and sdist once;
   each native shard also prepares an isolated wheel installation for its CLI tests.
   Native execution actions come from the trusted workflow commit, with the exact
   release source in a separate directory; historical actions cannot select caches.
   The final aggregate requires every quality gate and every selected native case.
   The PyPI job downloads those artifacts, checks any existing index files against
   their version, size and SHA-256, and uploads the missing files with Trusted
   Publishing. It then requires both files to match on PyPI before the GitHub job
   attaches the same artifacts and publishes the draft.

The publisher depends on successful verification of the draft's reported SHA. A
generally green branch or a successful job for a different commit is never accepted as
release evidence.

## Permissions and artifacts

The verification jobs have read-only repository permission and no publishing credentials. They run project code,
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
Aseprite distribution-risk follow-up remains with
[issue #126](https://github.com/aigengame/aseprite-automation/issues/126).

A draft/tag can already exist when verification fails. No PyPI upload or public
GitHub Release follows failed source checks, tests, Linux real Aseprite E2E, metadata
validation, package checks, or installed CLI verification.

## Recovery

- When manual verification needs a source change, merge the reviewed fix through
  routine CI, then dispatch a new Release verification from main. A new source
  requires new evidence; do not reinterpret the old run as testing the fix.
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
