# ADR-0098: Admit private native runners only through Release

## Status

Accepted by the owner on 2026-10-09. Runner deployment and GitHub scheduler
enforcement require separate live validation.

## Context

SPA is public. Its native tests need a separately supplied Aseprite installation;
GitHub binary caches make that installation accessible beyond the private host.
The owner selected direct GitHub Actions integration with a restricted self-hosted
runner for trusted Releases. Routine PR CI remains GitHub-hosted.

## Decision

- The organization group `spa-release` admits only this repository and jobs defined
  by `native-e2e-shards.yml@refs/heads/main`. The group restriction and review of
  main are deployment prerequisites. Labels alone do not restrict access.
- The reusable workflow runs a hosted admission job before scheduling native jobs.
  Inline admission code belongs to the trusted workflow revision, not to the
  caller's test target. It checks the exact caller repository, `release.yml` path,
  main ref, push/manual event and full Release SHA. Rejections fail explicitly.
- Automatic admission reads this run's Release record by ID, verifies its `target_commitish` SHA
  and requires it to be in the original main event's history. Manual admission
  accepts only the original event SHA. Neither recovery nor admission selects the
  current main head or latest release. Drafts need no existing Git tag; the pinned
  release-please action forwards the created Release ID.
- Native jobs use the admitted target output. A host-provisioned executable must
  pass the batch/script probe; no GitHub build, native download or binary cache
  fallback is permitted. Reports contain test evidence, not runtime installations.
- The existing shared `scripts/native_e2e.py` owns the local/Linux selection,
  configurable partition and evidence validation. Source quality and publication
  stay hosted. The existing strict aggregate requires every shard and complete
  exact-SHA evidence before either publisher can proceed.
- The old standalone Native E2E workflow remains disabled and cannot pass Release
  admission. The retained Build Aseprite workflow fails with host-provisioning
  instructions. Neither is a second route into the private group.

## Consequences

The official runner protocol supplies scheduling, logs, job status and dependency
gates. No SSH notification service or custom Checks/Statuses bridge is needed.
Main-only Release dispatch remains verification-only; merging the reviewed Release
PR remains publication approval.

Host provisioning, updates and execution capacity are administrator responsibilities.
Runner access must be tested before placing Aseprite on the host. Successful local
tests do not prove GitHub runner-group enforcement or Linux execution. Trusted-main
admission does not protect against malicious code approved into main or a compromised
runner host.

The verification allocation remains 40 minutes: preparation 3, admission 3, concurrent
shards 31, aggregation 3. Quality runs alongside admission and shards. Queue latency
is outside GitHub job timeouts; enough runner slots are needed for concurrent shards.
Operational setup and recovery are documented in [the testing guide](../testing.md#release-runner-setup).

## References

- [Distribution-risk follow-up #126](https://github.com/aigengame/aseprite-automation/issues/126)
- [GitHub reusable workflow context](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations#github-context)
- [GitHub runner-group access](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/manage-access)
- [GitHub rerun semantics](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs)
