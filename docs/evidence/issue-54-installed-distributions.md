# Installed distribution validation

This is bounded evidence for [#54](https://github.com/aigengame/aseprite-automation/issues/54),
recorded on 2026-10-07. The macOS checks passed. Validation of the current revision
on the selected Linux runner remains outstanding. This record does not certify
other platforms, later Aseprite releases, or public distribution of Aseprite.

## Selected profiles

| Profile | Aseprite acquisition | SPA installation | Current evidence |
| --- | --- | --- | --- |
| Local macOS 27.0.1 (26A434), Apple silicon arm64 | Caller-supplied `Aseprite-v1.3.18.5.app` | SPA 0.2.0 wheel, isolated CPython 3.13.13 environment with locked runtime dependencies | Passed the checks below |
| Existing GitHub `ubuntu-24.04` Linux X64 runner | Existing manual build/cache workflow; source release 1.3.18.5 and pinned build recipe | The existing native action builds and installs a separate wheel environment | Pending a run of the current revision; older success is historical evidence only |

The Linux source archive SHA-256 is
`04b0a84617efb3107d380c352ebb0af9eb2633ff4c1a8bfcb671d2a437247d5d`.
[The runtime action](../../.github/actions/aseprite-runtime/action.yml) owns the
pinned source and cache identity, including the build recipe hash. Its job summary
records the actual runner image, architecture, cache key, executable and reported
version. A cache miss follows the existing separate manual-build recovery path.
No build selector, trigger, budget or recovery policy changes for this issue.

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

[Native E2E run 37414803405](https://github.com/aigengame/aseprite-automation/actions/runs/37414803405)
and [CI run 37571290552](https://github.com/aigengame/aseprite-automation/actions/runs/37571290552)
did not start jobs. GitHub reported failed account payments or a spending limit.
Zero executed steps provide no package or runtime verification.

After that external block is resolved, run the existing Native E2E workflow for
this PR's merge result. Record its target SHA, actual runner/runtime facts,
package/resource verification and installed tracer outcomes before completing
#54. Recheck the source revision if it changes; a newer green job cannot be
inferred from an older result.

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
  public-repository Aseprite binary distribution decision. Private CI cache use
  here is not public distribution approval.
- [#189](https://github.com/aigengame/aseprite-automation/issues/189) owns PyPI
  publication. These local wheel checks do not publish a package or prove an
  installation from PyPI.
