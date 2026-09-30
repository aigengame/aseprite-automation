# PITFALLS — aseprite-automation

_Project-scoped operational guidance for agents. These entries are not universal
constraints. Apply an entry only when its **Applies when** condition matches the current
environment. Check the current execution environment first when that check is practical;
another environment can have different capabilities._

## Writable `uv`, `uvx`, and project environment paths in a managed sandbox

- **Applies when:** A managed environment reports that the default `uv` cache, tool
  directory, or project environment is not writable before the requested command
  starts.
- **Symptom:** `uv` reports that it failed to initialize its cache or acquire the
  project environment lock, or `uvx` fails while it prepares a tool environment.
- **Cause:** The default cache, tool directory, or project environment is outside the
  execution environment's writable paths.
- **Prevention:** Consider a task-scoped writable cache such as
  `UV_CACHE_DIR=<writable-temp-dir>/<task>-uv-cache`. An `uvx` command that installs a
  tool may also need `UV_TOOL_DIR=<writable-temp-dir>/<task>-uv-tools`. When the
  project environment is not writable, consider a unique absolute
  `UV_PROJECT_ENVIRONMENT=<writable-temp-dir>/<task>-venv`; do not share that environment
  between projects. On macOS or Linux, `/tmp/...` can be a suitable writable temporary
  location. Commands can reuse one task cache and project environment.
- **Recovery:** Rerun once with writable, task-scoped paths. For a read-only validation
  that does not need dependency synchronization, an existing environment's executable
  can be called directly after confirming that it belongs to the exact checkout. If the
  rerun reaches the requested command, treat the first failure as environment evidence
  rather than a product or test failure.
- **Last verified:** 2026-08-27 in a managed Codex desktop environment.

## Pytest and Ruff caches in a read-only worktree

- **Applies when:** Pytest or Ruff runs from a checkout or worktree that is readable
  but does not allow writes below its project root.
- **Symptom:** Tests can pass while pytest reports `PytestCacheWarning` for
  `.pytest_cache`; Ruff can fail before checking code because it cannot initialize
  `.ruff_cache`.
- **Cause:** Both tools write their own cache below the project root by default.
- **Prevention:** For pytest, if the cache is not needed, consider disabling its provider with
  `-p no:cacheprovider`. This also disables pytest's stepwise plugin. If the cache or
  stepwise behavior is needed, set a task-scoped writable location with
  `-o cache_dir=<writable-temp-dir>/<task>-pytest-cache`. For Ruff, use
  `RUFF_CACHE_DIR=<writable-temp-dir>/<task>-ruff-cache`.
- **Recovery:** Rerun with the applicable cache disabled or redirected. A pytest
  cache-write warning by itself does not prove that the test failed; a Ruff cache
  error prevents the check from running.
- **Last verified:** 2026-09-17 with Ruff and 2026-08-24 with pytest in managed
  read-only worktrees.

## Writable GitHub CLI cache for run evidence

- **Applies when:** A `gh run` command cannot read run logs or other CI evidence because
  the default local cache is not writable.
- **Symptom:** The command fails with an `operation not permitted` or similar local-cache
  error before it returns the requested GitHub data.
- **Cause:** The GitHub CLI is trying to use a cache path outside the execution
  environment's writable paths.
- **Prevention:** For the affected command, consider a task-scoped cache such as
  `XDG_CACHE_HOME=<writable-temp-dir>/<task>-xdg-cache`. On macOS or Linux,
  `/tmp/...` can be a suitable writable temporary location.
- **Recovery:** Retry the read with the writable cache. Distinguish a repeated GitHub or
  network error from the original local-cache failure.
- **Last verified:** 2026-08-27 in a managed Codex desktop environment.

## Restricted Git metadata during isolated work

- **Applies when:** An execution environment can read a checkout but cannot update its
  Git metadata.
- **Symptom:** `git fetch` cannot write `FETCH_HEAD`, or a linked-worktree command cannot
  update metadata even though the source files are readable.
- **Cause:** The environment protects `.git` or linked-worktree metadata outside its
  writable scope.
- **Prevention:** Check the available permission scope before planning a Git mutation.
  For read-only work, an existing exact commit object or an immutable GitHub snapshot may
  provide sufficient evidence.
- **Recovery:** For an authorized mutation, request the narrow permission that the Git
  operation needs. For read-only work, use a writable temporary clone or snapshot and
  record the exact commit that was inspected.
- **Last verified:** 2026-08 in managed review environments; recheck the current
  environment.

## GitHub connector and CLI permission differences

- **Applies when:** An authorized GitHub mutation through one integration returns
  `403 Resource not accessible by integration` while another authenticated GitHub path
  is available.
- **Symptom:** The integration can read the target but cannot post or edit the requested
  GitHub artifact.
- **Cause:** Integrations can use different tokens and permission scopes.
- **Prevention:** Check the permission scope of the GitHub path selected for the
  mutation. For Markdown-heavy content, a body file also avoids shell interpretation.
- **Recovery:** If the mutation is already authorized, consider an authenticated local
  `gh` CLI with the required permission. Read the target after an ambiguous failure or
  retry so the operation does not create a duplicate.
- **Last verified:** 2026-08 in managed GitHub workflows.

## Repository code versus an installed CLI

- **Applies when:** Validation runs a command name that can resolve to both the current
  checkout and a globally installed package.
- **Symptom:** The command reports stale behavior, a different version, or results that
  do not match the checked-out source.
- **Cause:** `PATH` selected an installed executable instead of the repository runtime.
- **Prevention:** Verify the executable and version before judging checkout behavior.
  Prefer the repository's documented environment, such as its local virtual environment
  or supported module entry point.
- **Recovery:** Rerun with the repository runtime selected explicitly and compare the
  result before classifying the change.
- **Last verified:** 2026-08 in another Python CLI repository.

## Direct macOS Aseprite bundle launch in a managed agent sandbox

- **Applies when:** A maintenance command or test in the verified managed macOS agent
  sandbox needs to run the executable at
  `<Aseprite.app>/Contents/MacOS/aseprite` directly, outside SPA's Runtime Integration
  adapter.
- **Symptom:** Even a minimal `--batch --script` invocation exits with status 134 and
  no stdout or stderr before the Lua script produces its expected output. Setting only
  `ASEPRITE_USER_FOLDER` to a writable directory does not resolve the failure.
- **Cause:** This sandbox profile requires SPA's prepared invocation layout: a launch
  symlink in a writable temporary workspace, adjacent linked Aseprite `data` resources,
  and a writable `ASEPRITE_USER_FOLDER`. Direct bundle invocation bypasses that
  environment-specific adaptation.
- **Prevention:** Use SPA's normal runtime path. When a repository maintenance script
  must invoke Aseprite directly, consider reusing
  `spa.adapters.aseprite.invocation.prepare_invocation()` with a task-scoped writable workspace
  instead of launching the bundle binary itself.
- **Recovery:** Retry the same script through `prepare_invocation()` and verify its
  expected output before classifying the failure as a Lua or Aseprite behavior defect.
  Do not assume this workaround applies outside the matching managed macOS profile.
- **Last verified:** 2026-09-21 with Aseprite 1.3.18.5 in a managed Codex desktop
  environment.

## GitHub CLI authentication does not satisfy SSH host-key verification

- **Applies when:** A Git remote uses an SSH URL, `gh` is authenticated for HTTPS Git
  operations, and the environment has not established trust for GitHub's SSH host key.
- **Symptom:** `git push` fails with `Host key verification failed` even though
  `gh auth status` reports an active account with repository access.
- **Cause:** GitHub CLI authentication and SSH host-key verification are separate. An
  HTTPS credential does not configure the SSH `known_hosts` trust record.
- **Prevention:** When bootstrapping a remote, use a Git URL that matches the protocol
  reported by `gh auth status`, unless SSH trust has already been configured according
  to the host's security policy.
- **Recovery:** Change the remote to the authenticated HTTPS URL and retry, or verify and
  install the official SSH host key through the environment's approved process. Do not
  disable strict host-key checking.
- **Last verified:** 2026-09-10 with Git and GitHub CLI in a managed macOS environment.

## Lowercase `path` is a special variable in zsh

- **Applies when:** A shell script or interactive command runs under zsh and assigns a
  scalar or array value to a variable named `path`.
- **Symptom:** Commands that worked earlier in the same shell start failing with
  `command not found`, including basic tools such as `git`, `awk`, or `gh`.
- **Cause:** In zsh, the lowercase `path` array is tied to the uppercase `PATH` scalar.
  Assigning `path` replaces the executable search path.
- **Prevention:** Use a task-specific variable name such as `artifact_path` or
  `spa_file`. Do not use lowercase `path` as a temporary variable in zsh commands.
- **Recovery:** Rename the variable and run the remaining commands in a fresh shell, or
  restore `PATH` from a known-good value before retrying. Treat the original failure as
  shell-environment evidence rather than evidence that each missing command was removed.
- **Last verified:** 2026-09-10 with zsh on macOS.

## Mermaid CLI cannot find or launch its browser

- **Applies when:** Mermaid CLI runs through a temporary `npx` environment that has no
  compatible downloaded browser, or a managed sandbox prevents Puppeteer from launching
  an installed browser.
- **Symptom:** Rendering fails before parsing the diagram with `Could not find
  chrome-headless-shell` or `Failed to launch the browser process`.
- **Cause:** Mermaid CLI uses Puppeteer for rendering. Its configured cache has no
  compatible browser executable, or the current permission scope blocks the browser
  process.
- **Prevention:** Confirm an available browser executable and set
  `PUPPETEER_EXECUTABLE_PATH=<browser-executable>`. Use an execution scope that permits
  the headless browser process when the managed environment requires it.
- **Recovery:** Retry the same render with the explicit browser path and required process
  permission. Treat a browser-launch failure as environment evidence, not Mermaid syntax
  evidence.
- **Last verified:** 2026-09-14 with Mermaid CLI 11.17.0 and local Chrome on macOS.

## Godot data-directory permissions and export-template discovery

- **Applies when:** Godot runs through gda in a managed environment that cannot write
  to the default application-data directory, or an export reuses a redirected data root.
- **Symptom:** Godot reports directory-creation errors during validation. After a data
  redirect, an export may no longer find templates installed in the normal location.
- **Cause:** The default data directory is outside the writable scope. gda's
  `--user-data-root` also changes the application-data location used to find Godot
  export templates.
- **Prevention:** For affected headless commands, put the global option
  `--user-data-root <writable-temp-dir>/<task>-godot-data` before the gda command.
  Before using that root for export, confirm that it has access to templates for the
  selected Godot version. A successful headless run does not establish template access.
- **Recovery:** Retry validation with the writable root and inspect the verdict and
  engine diagnostics. For export, use an authorized data location with the matching
  templates; changing the game or reinstalling gda does not repair this path mismatch.
- **Last verified:** Retained wizard v1/v2 runs on managed macOS with gda 0.19.0 and
  Godot 4.6.3; see [v1 export setup](examples/wizard_cast/README.md#verify-and-export-the-godot-consumer-with-gda)
  and [v2 H04](examples/wizard_cast_v2/DOGFOODING.md#h04--godot-needs-a-writable-data-location-in-the-managed-sandbox).

## A denied macOS window-server lookup does not establish display availability

- **Applies when:** A managed macOS process runs `gda daemon start --windowed` and
  cannot query the window server.
- **Symptom:** The command returns `live_windowed_permission_denied`, with
  `BOOTSTRAP_NOT_PRIVILEGED` in the lookup diagnostic.
- **Cause:** The execution scope denies the lookup. This result establishes a
  permission boundary; it cannot establish whether the host has a usable window server.
- **Prevention:** Check the diagnostic before classifying the host as headless. Use
  an authorized execution scope that permits the windowed process when one is available.
- **Recovery:** Obtain the required permission and retry the same launch. Classify
  the retry from its own result. Without that permission, report windowed validation
  as unverified; headless checks do not replace it.
- **Last verified:** The retained [v2 startup evidence](examples/wizard_cast_v2/evidence/godot-verification.json)
  records this failure and a successful approved retry on managed macOS with
  gda 0.19.0 and Godot 4.6.3.

## gda action state is not a key or mouse gesture

- **Applies when:** A Godot consumer handles key/mouse events or uses Buttons that
  activate on release, and automation tries `input action` or a lone button press.
- **Symptom:** The tool accepts the input request, but the event handler or Button
  callback does not run.
- **Cause:** In the verified gda version, `input action` defaults to changing polled
  action state, without sending a viewport event. A lone press also leaves a
  release-activated Button's gesture incomplete.
- **Prevention:** Match the input command to the consumer's handler. For key/mouse
  handlers, use key/mouse events; for a release-activated Button, use
  `input mouse-click` or a complete press/release sequence.
- **Recovery:** Release any input left held by the earlier attempt, then retry the
  complete event gesture. The wizard runs verified CAST and AGAIN clicks and paired
  Space/R key events through these routes.
- **Last verified:** Retained wizard v1/v2 runs with gda 0.19.0 and Godot 4.6.3; see
  [v1 input observations](examples/wizard_cast/DOGFOODING.md#gda-observations) and
  [v2 input commands](examples/wizard_cast_v2/evidence/godot-verification.json).
