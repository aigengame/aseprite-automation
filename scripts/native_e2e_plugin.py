"""Observe original pytest IDs and select one shard after normal marker filtering."""

import json
import os
from pathlib import Path

import pytest


class ShardEvidence:
    def __init__(self, config: pytest.Config) -> None:
        self.config = config
        self.collection: list[str] = []
        self.selected: list[str] = []
        self.workers: list[dict] = []
        self.outcomes: list[dict] = []
        self.output = Path(os.environ["SPA_E2E_SHARD_OUTPUT"])

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_collection_modifyitems(self, items: list[pytest.Item]):
        yield
        items.sort(key=lambda item: item.nodeid)
        self.collection = [item.nodeid for item in items]
        count = int(os.environ["SPA_E2E_SHARDS"])
        index = int(os.environ["SPA_E2E_SHARD_INDEX"])
        if len(set(self.collection)) != len(self.collection):
            raise pytest.UsageError("native collection contains duplicate test IDs")
        if count > len(items):
            raise pytest.UsageError(
                "native shard count exceeds the selected case count"
            )
        selected = items[index::count]
        self.selected = [item.nodeid for item in selected]
        chosen = set(self.selected)
        self.config.hook.pytest_deselected(
            items=[item for item in items if item.nodeid not in chosen]
        )
        items[:] = selected

    def pytest_testnodedown(self, node, error) -> None:
        self.workers.append(node.workeroutput.get("spa_e2e_collection", {}))

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if hasattr(self.config, "workerinput"):
            return
        if report.failed:
            (self.output / "failed").touch()
        if report.when == "call" or (
            report.when == "setup" and (report.failed or report.skipped)
        ):
            self.outcomes.append({"nodeid": report.nodeid, "outcome": report.outcome})

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        if hasattr(self.config, "workerinput"):
            self.config.workeroutput["spa_e2e_collection"] = {
                "collection": self.collection,
                "selected": self.selected,
            }
            return
        (self.output / "pytest.json").write_text(
            json.dumps(
                {
                    "workers": self.workers,
                    "outcomes": self.outcomes,
                    "exit_code": int(exitstatus),
                }
            )
        )


def pytest_configure(config: pytest.Config) -> None:
    config.pluginmanager.register(ShardEvidence(config), "spa-native-shard-evidence")
