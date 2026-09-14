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

## Pytest cache in a read-only worktree

- **Applies when:** Pytest runs from a checkout or worktree that is readable but does
  not allow writes below its project root.
- **Symptom:** Tests can pass, but pytest reports `PytestCacheWarning` because it cannot
  write a path below `.pytest_cache`.
- **Cause:** The built-in cache provider stores node IDs, failure state, and related
  data in `.pytest_cache` by default.
- **Prevention:** If the cache is not needed, consider disabling the provider with
  `-p no:cacheprovider`. This also disables pytest's stepwise plugin. If the cache or
  stepwise behavior is needed, set a task-scoped writable location with
  `-o cache_dir=<writable-temp-dir>/<task>-pytest-cache`.
- **Recovery:** Rerun with the cache disabled or redirected when a warning-free result
  is required. A cache-write warning by itself does not prove that the test failed.
- **Last verified:** 2026-08-24 with pytest in a managed read-only worktree.

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
