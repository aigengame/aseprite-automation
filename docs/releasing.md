# Releases

SPA uses a reviewed Release PR and an exact-commit manual release workflow. The
current publisher creates a GitHub Release with a Python source distribution and
wheel. PyPI publication is outside this phase.

## Release authorities

- `release-please-config.json` defines versioning, changelog sections, tag shape, and
  the `uv.lock` version update.
- `.release-please-manifest.json` records the latest reviewed release version.
- The Release PR owns the coordinated `pyproject.toml`, manifest, `uv.lock`, and
  `CHANGELOG.md` change.
- `.github/workflows/release.yml` verifies and publishes one exact commit. It never
  chooses or edits a version.

The `Release PR` workflow runs on pushes to `main`. It uses release-please only to
create or update the reviewable change; it cannot create a tag or GitHub Release.
Because it uses the repository `GITHUB_TOKEN`, its bot-authored updates do not trigger
another workflow. Review the complete Release PR and rely on the exact-commit Release
verification after merge.

## Verification environments

Local real-runtime evidence normally uses the installed macOS Aseprite application.
CI and release verification use Linux and build the pinned official Aseprite 1.3.18.5
source with scripting enabled and the non-graphical backend. The Linux gate requires
`DISPLAY` and `WAYLAND_DISPLAY` to be absent, exercises the real `--batch --script`
probe, and rejects zero or all-skipped E2E execution.

These results answer different platform questions. Linux headless success does not
cover the macOS bundle or restricted-agent launch path. Neither environment currently
claims windowed Aseprite coverage. See [the test suite guide](testing.md) for the exact
commands and skip policy.

## Prepare and verify a release

1. Merge ordinary changes through CI.
2. Review the Release PR. Confirm that its version, changelog, manifest, project
   metadata, and lockfile agree, then merge it.
3. From the Actions page, run `Release` on `main` with `publish` left false. Record the
   successful run before the first public release. This exercises source checks, fast
   tests, the Linux real Aseprite E2E gate, package build, metadata checks, and the
   installed-wheel smoke test without creating a release.
4. Run `Release` again on `main` with `publish` true. The workflow repeats every gate
   at the dispatch SHA, validates the reviewed release metadata, and builds the wheel
   and sdist once.

The publishing run checks that `main` still points to the verified SHA. Release-please
then creates a draft for that SHA. The workflow compares the draft SHA with the tested
SHA before the publisher can run. A generally green branch or a successful job for a
different commit is never accepted as release evidence.

## Permissions and artifacts

The verification job has read-only repository permission. It runs project code,
native Aseprite, tests, and the build backend, then stores the exact-SHA distributions
as a run-scoped artifact. The draft-cutting job has only repository release and pull
request permissions and runs no checked-out project code. The final publisher has
only repository contents permission; it downloads the already verified artifact,
attaches exactly one wheel and one sdist, and publishes the draft.

No tag or public release is created when source checks, tests, Linux real Aseprite E2E,
metadata validation, package checks, or the installed CLI smoke test fail.

## Recovery

- When verification fails, fix the cause through a pull request and start a new run on
  the new `main` SHA. No draft was created.
- When draft creation fails before a release exists, use **Re-run failed jobs** after a
  transient GitHub failure. The SHA guard still applies.
- When asset upload or draft publication fails, use **Re-run failed jobs**. The
  successful verification and draft jobs remain fixed, and `gh release upload
  --clobber` makes the publisher converge on the same two artifacts.
- Do not rerun every job after a draft was created. A full rerun can ask
  release-please to cut the same untagged release again. Resume only failed jobs.
- When `main` advances between verification and draft creation, the run fails. Start a
  new run so the tests, Aseprite E2E evidence, distributions, and release SHA agree.
