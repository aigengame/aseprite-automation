---
status: accepted
---

# Keep caller-supplied raw Lua separate from ordinary operations

`script run` exposes Aseprite's native script execution as an explicit unrestricted capability. It accepts either an existing caller-owned `.lua` file or Lua source supplied on stdin. Because Aseprite requires `--script <filename>`, SPA may materialize the exact stdin bytes as a temporary `.lua` file for the invocation.

Materialization is transport, not implementation generation. SPA does not modify, concatenate, template, wrap, or inject behavior into the caller's source. The resulting Caller Script never becomes a packaged handler, does not enter the Lua Operation Kernel, and cannot be used by an ordinary Operation or Operation Plan as an alternate execution path.

`script run` has the distinct `script-run` Execution Kind and is excluded from Plan Steps. Its structured result identifies raw-script execution and does not claim the behavior, transaction, target-addressing, mutation-safety, or result semantics of ordinary Kernel Operations. File and stdin forms execute the caller's program under the same explicitly unrestricted capability.

This exception preserves a useful native Aseprite escape hatch for agents without weakening the rule that all ordinary Core Operation Semantics live in fixed, versioned, packaged Lua Kernel handlers.
