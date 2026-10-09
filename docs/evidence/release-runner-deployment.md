# Release runner deployment evidence

## Access checks — 2026-10-09

The tested main commit is `5be35736703e5d45e6a2fa02f5ddb755017cdbc7`
([PR #198](https://github.com/aigengame/aseprite-automation/pull/198)). The host
runs Ubuntu 24.04 on ARM64, with two CPUs and 12 GB allocated memory. Runner
`spa-arm64-01` has ID `165` in organization group `spa-release` (ID `3`). Its
systemd service runs as a dedicated ordinary account and starts at boot.

The owner supplied expanded settings screenshots confirming one selected repository,
`aigengame/aseprite-automation`, public repository access, and one selected workflow:

```text
aigengame/aseprite-automation/.github/workflows/native-e2e-shards.yml@refs/heads/main
```

The local GitHub credential cannot read organization runner settings. Screenshots
establish the configured allowlist; the following live runs establish observed
behavior. Aseprite was absent throughout these access checks.

| Case | Evidence | Observed result |
| --- | --- | --- |
| Manual Release from main | [Run 37908310495, job 113747161868](https://github.com/aigengame/aseprite-automation/actions/runs/37908310495/job/113747161868) | Hosted admission passed. Runner 165 in group 3 executed the shard, then failed at the missing `SPA_TEST_ASEPRITE` check. |
| Allowed control while negative probes waited | [Same run, attempt 2, job 113749549031](https://github.com/aigengame/aseprite-automation/actions/runs/37908310495/job/113749549031) | The same runner executed the shard from 09:05:51 to 09:06:19 UTC. It failed at the same runtime check. |
| Direct group request from branch push | [Run 37908789199](https://github.com/aigengame/aseprite-automation/actions/runs/37908789199) | Unassigned from 09:03:12 until cancellation at 09:07:28 UTC; runner ID 0 and no executed steps. |
| Direct group request from PR #199 | [Run 37908924525](https://github.com/aigengame/aseprite-automation/actions/runs/37908924525) | Unassigned from 09:04:28 until cancellation at 09:07:32 UTC; runner ID 0 and no executed steps. |
| Other caller invokes the selected reusable workflow | [Push run 37908789737](https://github.com/aigengame/aseprite-automation/actions/runs/37908789737), [PR run 37908924836](https://github.com/aigengame/aseprite-automation/actions/runs/37908924836) | Hosted admission explicitly rejected the caller. Native shard jobs were skipped and had no runner assignment. |
| Current Release dispatched outside main | [Run 37908918818](https://github.com/aigengame/aseprite-automation/actions/runs/37908918818) | The prepare job reported `Release verification must run from main`; the native path and publication jobs were skipped. |

The negative probe commit was `fa5771f8e50cc2393a24bbeab4c85d5c2b892677` on
`codex/release-runner-validation`. Direct probes contained only a fixed failure
marker and `exit 1`, with `permissions: {}` and no checkout. Their final cancelled
job records still contained no assignment or steps. The host journal recorded
only the two allowed native shard jobs.

The selected allowlist, simultaneous allowed control, and unassigned push/PR probes
are consistent with workflow restriction enforcement. GitHub did not expose an
explicit authorization error for the direct probes: **queue state alone is not
proof of its cause**. GitHub documents that jobs without an eligible runner remain
queued. A [reported support case](https://depot.dev/blog/troubleshooting-github-actions-unexpected-behaviors)
also records this behavior for a selected-workflow ref mismatch.

The caller test checks a separate boundary. GitHub permits jobs directly defined in
the selected reusable workflow; SPA's hosted admission rejects unauthorized callers
before those private jobs can run. See [GitHub's group access rules](https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/manage-runners/self-hosted-runners/manage-access).

## Limits and cleanup

- These are deployment access checks, not successful native E2E results. The
  allowed main run's remaining quality work was cancelled after scheduling was
  established. Its failed shard was rerun alone for the control experiment.
- The PR probe used a same-repository branch. No external fork was created. The
  non-main dispatch used the current workflow on the validation branch; the older
  workflow on `dev` was not dispatched. These untested scenarios are not claimed
  as separate live results.
- All queued probes were cancelled and their final job records checked. Both
  temporary workflows were disabled and removed from the branch. Release and
  Native E2E shards were returned to their disabled state after these checks.
- No publication occurred. No Aseprite binary was built, cached, or uploaded by
  these workflows. Registration credentials and host configuration files were
  not copied into the repository or public evidence.
- Local regression checks passed: 30 admission/publication tests and four
  host-runtime tests. Both temporary workflows passed `actionlint` before use.

Runtime provisioning and complete Linux E2E validation follow these access checks.
The deployment contract remains in [ADR-0098](../adr/0098-release-only-private-native-runner.md)
and the [testing guide](../testing.md#release-runner-setup).
