# Releases

SPA uses a reviewed Release PR and an exact-commit automatic release workflow. The
current publisher creates a GitHub Release with a Python source distribution and
wheel. PyPI publication is outside this phase.

## Release authorities

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
draft's exact commit, builds the distributions, attaches them, and publishes the
GitHub Release. It maintains the next Release PR only after the tag exists. This
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

The verification job uses GitHub's native **40-minute timeout**, including runtime
setup, all tests, quality/package checks, and uploads. It does not compile Aseprite
or subtract time. A missing or invalid binary fails the gate and prevents publication.
Run the separate **Build Aseprite** workflow as described in
[manual Aseprite recovery](testing.md#restore-the-aseprite-runtime), then
re-run the original failed Release run to preserve its exact SHA and release tail.
A maintenance success does not authorize publication. The 40-minute limit applies
to the verification job; draft creation and publication are separate jobs.

The [issue #107 capacity measurements](evidence/issue-107-ci-capacity.md) retain
historical experiments separately from the current cache-only verification policy.

These results answer different platform questions. Linux headless success does not
cover the macOS bundle or restricted-agent launch path. Neither environment currently
claims windowed Aseprite coverage. See [the test suite guide](testing.md) for the exact
commands and skip policy.

## Prepare and publish a release

1. Merge approved ordinary PRs into `dev` after review, routine CI, and affected
   local checks. Run [Native E2E once after the integration batch](testing.md#native-e2e-after-an-integration-batch)
   and verify its final commit before promotion. Promotion PRs retain the explicit
   current-merge Native E2E check.
2. Review the Release PR. Confirm that its version, changelog, manifest, project
   metadata, and lockfile agree, its routine CI passes, and pre-merge Native E2E
   passed for the current base/head/merge target.
3. Before the first public release, select the Release PR branch on the Actions page
   and manually run `Release`. A manual run is verification-only: it exercises source
   checks, fast tests, the Linux real Aseprite E2E gate, package build, metadata checks,
   and the installed-wheel smoke test without creating a draft, tag, or release.
4. Merge the Release PR. The resulting `main` push creates the draft and reports its
   exact commit. The read-only verification job checks out that commit, repeats every
   gate, validates the reviewed release metadata, and builds the wheel and sdist once.
   The publisher then attaches those artifacts and publishes the GitHub Release.

The publisher depends on successful verification of the draft's reported SHA. A
generally green branch or a successful job for a different commit is never accepted as
release evidence.

## Permissions and artifacts

The verification job has read-only repository permission. It runs project code,
native Aseprite, tests, and the build backend, then stores the exact-SHA distributions
as a run-scoped artifact. The draft-cutting job has only repository release and pull
request permissions and runs no checked-out project code. The final publisher has
repository contents permission for the existing draft and read access to the verified
run artifact. It downloads that artifact, attaches exactly one wheel and one sdist,
and publishes the draft. A separate post-release job owns the permissions needed to
maintain the next Release PR and dispatch its CI.

No tag or public release is created when source checks, tests, Linux real Aseprite E2E,
metadata validation, package checks, or the installed CLI smoke test fail.

## Recovery

- When a manual non-publishing verification fails, fix the Release PR branch and run
  the verification again on its new head.
- When Release PR maintenance fails after release-please creates or updates the PR,
  use **Re-run failed jobs**. The maintenance action resolves the existing open
  Release PR, regenerates and validates its lockfile, verifies its remote head, and
  dispatches exact-head CI even when release-please has no new PR update to report.
- When verification fails after a draft was cut, use **Re-run failed jobs** after the
  cause is corrected without changing the reviewed release commit. The publisher is
  deliberately marked failed too, so both jobs resume while the successful draft job
  remains fixed.
- When draft creation fails before a release exists, use **Re-run failed jobs** after a
  transient GitHub failure.
- When asset upload or draft publication fails, use **Re-run failed jobs**. The
  successful verification and draft jobs remain fixed, and `gh release upload
  --clobber` makes the publisher converge on the same two artifacts.
- Do not rerun every job after a draft was created. A full rerun can ask
  release-please to cut the same untagged release again. Resume only failed jobs.
