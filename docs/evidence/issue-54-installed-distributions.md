# Installed distribution validation

This is bounded evidence for [#54](https://github.com/aigengame/aseprite-automation/issues/54),
recorded on 2026-10-07. The macOS checks passed. Validation of the current revision
on the selected Linux runner remains outstanding. This record does not certify
other platforms, later Aseprite releases, or public distribution of Aseprite.

## Policy update — 2026-10-09

[ADR-0098](../adr/0098-release-only-private-native-runner.md) supersedes the former
GitHub-hosted Linux build/cache profile and standalone PR Native E2E procedure.
The current Linux path is trusted Release verification on a privately provisioned
runner. Its host facts and installed-wheel results remain unverified; the macOS
results and historical Linux receipts below retain their original dates and SHAs.
[Runner setup](../testing.md#release-runner-setup),
[host repair](../testing.md#restore-the-aseprite-runtime) and the
[release guide](../releasing.md) own the current operating procedures.

## Selected profiles

| Profile | Aseprite acquisition | SPA installation | Current evidence |
| --- | --- | --- | --- |
| Local macOS 27.0.1 (26A434), Apple silicon arm64 | Caller-supplied `Aseprite-v1.3.18.5.app` | SPA 0.2.0 wheel, isolated CPython 3.13.13 environment with locked runtime dependencies | Passed the checks below |
| Private Release-only Linux runner in `spa-release` | Administrator-provisioned Aseprite outside checkout and cache paths, selected by `SPA_TEST_ASEPRITE` | The existing native action builds and installs a separate wheel environment for the admitted SHA | Pending deployment and execution; record actual OS, architecture, binary provenance and runtime results |

The superseded Linux profile selected on 2026-10-06 used GitHub `ubuntu-24.04`
X64, source release 1.3.18.5 and source archive SHA-256
`04b0a84617efb3107d380c352ebb0af9eb2633ff4c1a8bfcb671d2a437247d5d`.
Its runtime action then owned the pinned source/cache identity and manual-build
recovery. These are historical provenance facts, not the current acquisition
procedure. The current runtime action probes a host-supplied executable and does
not build, download or cache Aseprite. No Linux host profile is certified by this
policy update.

## macOS package and source

- Package source: `7fabeabd45d6450e752cfeebb95035e398aca72a`.
- Verification changes for this issue affect scripts, tests and native-action
  wiring, with no changes to `src/spa`, package metadata,
  locked dependencies or the Skill.
- Wheel: `aseprite_automation-0.2.0-py3-none-any.whl`, 538,788 bytes,
  SHA-256 `5a3bd6f0de2c92310d39b95470cbf4bf200c564d1d85897c7c8235a70005dad0`.
- Source distribution: `aseprite_automation-0.2.0.tar.gz`, 417,576 bytes,
  SHA-256 `3b31e815e29d103fb1c5dde2e5ed15b701547b1220884941d809b8ba3a791e59`.
- `uv build` built the wheel from the source distribution. Both passed
  `twine check`. Runtime dependencies came from the frozen lockfile, without
  development or MCP dependencies.
- The package loaded from the temporary wheel environment's
  `lib/python3.13/site-packages/spa`. Native consumer calls ran outside the
  checkout, with `PYTHONPATH` removed. No editable install supplied these results.
- All 251 Python and Kernel source files were also compared byte for byte with
  the built wheel. Ruff lint/format and Pyright passed for the checkout.

The installed verifier checked the version and all **143** Kernel resources
(`.lua`, `.aseprite`, `.icc`) against their source paths and SHA-256 digests.
It rejects editable installs, imports outside the selected isolated environment,
empty resources and unresolved Git LFS pointers. The wheel contains no Skill copy.

## Real installed CLI tracer

The caller supplied
`~/Applications/Aseprite-v1.3.18.5.app/Contents/MacOS/aseprite`.
The installed `spa info` resolved that executable and its sibling
`Contents/Resources/data/gui.xml`; it reported `resource_complete: true`,
Aseprite **1.3.18.5-dev**, scripting API **41**, and **Lua 5.4**. The source release
name and the executable's reported version are recorded separately.

The real `--batch --script` probe verified scripting, Lua file I/O and native JSON.
It reported 65 verified Runtime Capabilities and 30 declared Capability Gaps.
The gaps include native text rasterization, unsupported paint tools and bounded
filter, composite and Slice cases; they do not block this Phase 1 tracer.
The macOS runtime verified native color-profile conversion. The historical Linux
headless build lacks that converter and reports a corresponding discovery gap;
the current Linux result must be recorded from its own run.

| Existing test path | Installed-wheel evidence |
| --- | --- |
| `tests/runtime/test_e2e_aseprite.py::test_wheel_installed_info_discovers_real_runtime` | Successful `spa info`, installed Result schema, executable/resource discovery, required prerequisites and explained Capability Gaps |
| `tests/plan/test_e2e_plan.py::test_wheel_installed_plan_uses_packaged_handler` | Create a 2×2 RGB Sprite, set Cel opacity, apply a red Pixel Patch, inspect Cels and validate Plan postconditions; save/reopen verified and Target digest checked |
| `tests/export/test_e2e_export_image.py::test_wheel_installed_cli_exports_verified_image` | Installed PNG export; independent Pillow decoding checks the native source fixture's expected RGBA pixel |
| `tests/sprite/test_e2e_sprite.py::test_wheel_installed_handler_rejection_is_schema_valid_without_target_commit` | Typed failure when the Target parent is a file, with no Target Commit or file mutation |

The bounded selection passed: **4 passed, 35 deselected in 4.44 seconds**.
Deselected tests were outside this installation tracer. This is not a claim that
the full native suite or example rebuilds ran.

Additional controlled checks against the temporary installation passed:

- Selecting the project editable installation failed with
  `installed verification requires a wheel, not an editable install`.
- Replacing one installed fixture with an LFS pointer failed with its exact
  resource name. The original bytes were restored and the verifier passed again.
- Selecting a missing runtime produced exit 1 and typed `executable_not_found`.

These checks found a verifier gap: before this change, the same editable
installation incorrectly passed the script's installation check. No SPA product
behavior changed to address that verification gap.

## Reproduce through the existing paths

From the tested checkout, choose a fresh temporary directory and use the locked
runtime dependencies. `SPA_VERIFY_ROOT` and `SPA_TEST_ASEPRITE` below are explicit
caller choices; neither has a new product default.

```sh
export SPA_VERIFY_ROOT=/absolute/path/to/fresh/temporary-directory
export SPA_TEST_ASEPRITE=/absolute/path/to/aseprite
uv build --out-dir "$SPA_VERIFY_ROOT/dist"
uv run --frozen twine check "$SPA_VERIFY_ROOT"/dist/*
uv export --quiet --frozen --no-dev --no-emit-project \
  --output-file "$SPA_VERIFY_ROOT/runtime-requirements.txt"
uv venv "$SPA_VERIFY_ROOT/wheel-env" --python 3.13
uv pip sync --python "$SPA_VERIFY_ROOT/wheel-env/bin/python" \
  --require-hashes "$SPA_VERIFY_ROOT/runtime-requirements.txt"
uv pip install --python "$SPA_VERIFY_ROOT/wheel-env/bin/python" \
  --no-deps "$SPA_VERIFY_ROOT"/dist/*.whl
export SPA_TEST_INSTALLED_CLI="$SPA_VERIFY_ROOT/wheel-env/bin/spa"
uv run --frozen python scripts/verify_installed_cli.py "$SPA_TEST_INSTALLED_CLI"
uv run --frozen --group test pytest \
  tests/runtime/test_e2e_aseprite.py tests/plan/test_e2e_plan.py \
  tests/export/test_e2e_export_image.py tests/sprite/test_e2e_sprite.py \
  -k wheel_installed -q
```

The Linux native action now calls the same resource verifier immediately after
its isolated wheel installation. Its existing `e2e and not slow` selection
includes these four cases. It requires `DISPLAY` and `WAYLAND_DISPLAY` to be
absent and uses the existing real batch runtime. This issue adds no workflow,
full-suite duplicate or platform/version matrix. Ordinary distribution checks
still run without Aseprite; they are package evidence only.

## Linux evidence still required

[Native E2E run 37307931682](https://github.com/aigengame/aseprite-automation/actions/runs/37307931682)
passed on 2026-10-05 for PR #181's merge preview
`8b427dbc1903449ff5c9d194b1fa622b9bf310e2`. It used Linux X64, Ubuntu 24.04 and
Aseprite 1.3.18.5-dev. That SHA predates the current package and these checks;
it cannot satisfy #54's current-revision Linux acceptance criterion.

[PR #190 CI run 37582628552](https://github.com/aigengame/aseprite-automation/actions/runs/37582628552)
and [Native E2E run 37582700255](https://github.com/aigengame/aseprite-automation/actions/runs/37582700255)
did not start jobs. Both reported failed account payments or a spending limit.
All three CI jobs had zero steps; the native target resolver also had zero
steps, so no merge SHA was resolved and no native shard executed. This attempt
was made for PR head `e05516272a97d46a3d1a54d139970a01a052ebc3`. Zero executed
steps provide no package or runtime verification.

After [PR #198](https://github.com/aigengame/aseprite-automation/pull/198) merges,
follow the setup procedure above: first validate
allowed/denied scheduling without Aseprite, then provision the host runtime and
run main Release verification for its admitted exact SHA. Manual Release runs
verify the original event SHA without publishing. Record the actual runner/runtime
facts, package/resource verification, installed tracer outcomes and Capability
Gaps for that revision. Missing or unusable Aseprite requires host repair, followed
by the original Release jobs; the retired builder and standalone PR workflow cannot
supply this evidence. This is deployment validation, not a new gate before the
code PR can merge. #54's owner-requested closure did not establish a Linux pass;
earlier results do not prove a later revision or a different host profile.

## Separate delivery evidence

- [#52 Skill evidence](issue-52-agent-skill.md) records Skills CLI 1.7.0 and a real
  Codex project-scope copy installation/use workflow at Skill source revision
  `89a59c2c0b5f8933804187269731acf0d245675b`. The current Skill has the same SHA-256
  `d57b7abf997387e56290f7cba2d2909e34e30269aa550a5444d987b0f78aeb2f`.
  That bounded macOS agent evidence is reused; no Linux agent run, other agent
  target, Skill version equality or external compatibility verdict is claimed.
- [#53 MCP evidence](issue-53-mcp.md) owns optional MCP installation, protocol
  and real-client checks. The base CLI wheel test does not replace it.
- [#126](https://github.com/aigengame/aseprite-automation/issues/126) owns the
  public-repository Aseprite binary distribution decision. The historical private
  CI cache use recorded here is not public distribution approval; the current
  Release path does not cache or upload the runtime.
- [#189](https://github.com/aigengame/aseprite-automation/issues/189) owns PyPI
  publication. These local wheel checks do not publish a package or prove an
  installation from PyPI.
