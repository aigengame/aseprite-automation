# Test suite

SPA organizes tests first by the behavior owner and then names each test file by its
verification tier. The layout does not mirror source packages or CLI Command Groups.

## Ownership areas

| Directory | Behavior owner |
| --- | --- |
| `tests/cli/` | Access Projection through the installed CLI and its in-process projections. |
| `tests/contracts/` | Shared Published Language rules, including Failure Code registration and Operation Descriptor constraints. |
| `tests/delivery/` | CI and release gates that protect source and distribution delivery. |
| `tests/runtime/` | Aseprite Runtime Integration, including discovery, launch, private Kernel transport, and real-runtime evidence. |

Add an ownership directory only when tests for that behavior exist. Keep a helper in
the narrowest ownership directory that uses it. Move a helper to `tests/support.py`
only when more than one ownership area needs it. Each directory is a Python package,
so different owners can safely use the same focused file name later.

## Verification tiers

Use the tier in the file name:

- `test_unit_*.py` exercises rules and contracts in one process.
- `test_integration_*.py` connects SPA components. It can invoke the installed `spa`
  CLI with a controlled fake Aseprite executable, but it does not prove native
  Aseprite behavior.
- `test_e2e_*.py` invokes the installed `spa` CLI with a real Aseprite executable.
  Mark the module or each test with `pytest.mark.e2e`.

Pytest rejects unregistered markers. The root e2e gate also rejects a selected e2e
test when `SPA_TEST_ASEPRITE` is absent, is not a file, or is not executable. A missing
runtime therefore cannot produce an all-skipped successful e2e run.

Run the fast unit and integration tiers with:

```sh
uv run --frozen --group test pytest -m "not e2e"
```

Run the real-runtime tier with:

```sh
SPA_TEST_ASEPRITE=/path/to/aseprite \
  uv run --frozen --group test pytest -m e2e -rs
```

Use `-rs` so platform and environment skips remain visible. Use collection output when
moving tests to confirm that parametrized cases were preserved:

```sh
uv run --frozen --group test pytest --collect-only -q
```

Run the same source checks used by CI with:

```sh
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
```

`pyright` checks production code under `src/`. Runtime tests deliberately construct
invalid and partially controlled values, so their correctness is enforced by pytest
instead of the production type gate.

## CI gates

`.github/workflows/ci.yml` runs on every pull request and every push to `main`. All
jobs use Python 3.13, uv 0.11.19, and the committed `uv.lock` with `--frozen`.

| Job | Required evidence |
| --- | --- |
| Source quality | Ruff lint and formatting plus Pyright for production source. |
| Fast tests | Unit and integration tests selected with `-m "not e2e"`. |
| Build and smoke test distributions | One sdist and wheel, valid package metadata, and a successful `spa version` from a wheel-only environment. |
| Linux real Aseprite E2E | The installed SPA CLI drives the pinned real Aseprite `--batch --script` path and records JUnit evidence. |

A failure in any job fails CI. Configure these four named jobs as required checks on
`main` when repository branch protection is enabled.

## Platform and display requirements

Verification tier, host platform, and display capability are separate properties.
Place a platform condition on the smallest test that needs it. A passing macOS test is
macOS evidence; it is not Linux evidence. The macOS bundle and restricted-agent cases
remain macOS-specific. Issue #69 owns Linux CI and Linux real-Aseprite evidence.

Aseprite `--batch` does not start the UI. A test that produces or inspects image files
through that path is not windowed unless it actually needs a display. When a future
test does require a window, declare that precondition at the test boundary and add a
shared display gate only when more than one test needs it. An optional run on a host
without display capability can skip with a visible reason. Display permission denial
must fail. A job that claims graphical coverage must fail when its required windowed
tests do not execute.

The Linux job builds the official Aseprite 1.3.18.5 source release whose SHA-256 is
`04b0a84617efb3107d380c352ebb0af9eb2633ff4c1a8bfcb671d2a437247d5d`.
It enables scripting with Aseprite's `LAF_BACKEND=none`, checks that both `DISPLAY` and
`WAYLAND_DISPLAY` are absent, and then runs the real-runtime tier. The JUnit audit fails
when the report is missing, contains zero tests, or all selected tests were skipped.
The job summary records the commit, trigger, executable, Aseprite version, display
state, and exercised path. A macOS-only skip remains visible and does not invalidate
the Linux batch evidence while other E2E tests execute.

The Linux real Aseprite job is also part of release verification. A release workflow
always reruns it at the exact release commit and does not reuse a generally green CI
run. A successful macOS local run remains separate developer evidence; it cannot
replace the Linux release gate. Windowed Aseprite behavior has no CI coverage until a
dedicated display-capable job is added with an execution-count gate.
