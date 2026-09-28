#!/usr/bin/env bash
# Dispatch CI only after the Release PR reports the pushed commit.
set -euo pipefail

expected_sha="$(git rev-parse HEAD)"
for attempt in {1..10}; do
  observed_sha="$(gh pr view "$SPA_RELEASE_PR_NUMBER" --repo "$GITHUB_REPOSITORY" \
    --json headRefOid --jq .headRefOid)"
  if [ "$observed_sha" = "$expected_sha" ]; then
    break
  fi
  echo "Release PR #$SPA_RELEASE_PR_NUMBER: expected $expected_sha; observed $observed_sha (attempt $attempt/10)." >&2
  if [ "$attempt" -lt 10 ]; then
    sleep 2
  fi
done
if [ "$observed_sha" != "$expected_sha" ]; then
  echo "Release PR head did not converge; CI was not dispatched." >&2
  exit 1
fi
gh workflow run ci.yml --repo "$GITHUB_REPOSITORY" --ref "$SPA_RELEASE_BRANCH"
echo "Dispatched CI for exact head \`${expected_sha}\`." >> "$GITHUB_STEP_SUMMARY"
