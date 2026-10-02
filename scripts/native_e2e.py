"""One native test selection, partition, and evidence gate for local and CI runs."""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from verify_pytest_execution import execution_counts

SELECTION = "e2e and not slow"


@dataclass(frozen=True)
class Configuration:
    shards: int = 2
    workers: int = 2

    def __post_init__(self) -> None:
        if self.shards < 1 or self.workers < 1:
            raise ValueError("shards and workers must be positive integers")

    def command_args(self) -> list[str]:
        return ["--shards", str(self.shards), "--workers", str(self.workers)]


def source_target(path: Path | None) -> dict:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    target = json.loads(path.read_text()) if path else {"kind": "local", "sha": sha}
    if target.get("sha") != sha:
        raise ValueError("native target SHA does not match the checked-out source")
    return target


def check_report(path: Path, config: Configuration, target: dict) -> dict:
    report = json.loads(path.read_text())
    if report["target"] != target or any(
        report[key] != value
        for key, value in (
            ("shards", config.shards),
            ("workers", config.workers),
            ("selection", SELECTION),
            ("exit_code", 0),
        )
    ):
        raise ValueError(f"failed or mismatched native report: {path}")
    collection = report["collection"]
    if not collection or sorted(set(collection)) != collection:
        raise ValueError(f"invalid full collection: {path}")
    index = report["shard_index"]
    if not 0 <= index < config.shards:
        raise ValueError(f"invalid shard index: {path}")
    outcomes = report["outcomes"]
    if Counter(o["nodeid"] for o in outcomes) != Counter(
        collection[index :: config.shards]
    ):
        raise ValueError(f"missing or duplicate native outcomes: {path}")
    if any(o["outcome"] not in ("passed", "skipped") for o in outcomes):
        raise ValueError(f"unsuccessful native outcome: {path}")
    total, skipped, executed = execution_counts(path.with_name("junit.xml"))
    print(
        f"JUnit execution: total={total} skipped={skipped} executed={executed}",
        flush=True,
    )
    if executed == 0:
        raise ValueError("real Aseprite E2E gate executed no tests")
    if total != len(outcomes) or skipped != sum(
        o["outcome"] == "skipped" for o in outcomes
    ):
        raise ValueError(f"JUnit and original native outcomes disagree: {path}")
    return report


def verify(output: Path, config: Configuration, target: dict) -> None:
    paths = sorted(output.glob("shard-*/result.json"))
    if len(paths) != config.shards:
        raise ValueError("missing or extra native shard reports")
    reports = [check_report(path, config, target) for path in paths]
    if sorted(r["shard_index"] for r in reports) != list(range(config.shards)):
        raise ValueError("missing or duplicate native shard indices")
    collection = reports[0]["collection"]
    if any(r["collection"] != collection for r in reports):
        raise ValueError("native shards collected different complete suites")
    outcomes = [o for r in reports for o in r["outcomes"]]
    if Counter(o["nodeid"] for o in outcomes) != Counter(collection):
        raise ValueError("native shard union is incomplete or duplicated")
    counts = Counter(o["outcome"] for o in outcomes)
    print(
        f"Native E2E: selected={len(collection)} passed={counts['passed']} "
        f"skipped={counts['skipped']} sha={target['sha']}",
        flush=True,
    )


def run_shard(output: Path, config: Configuration, index: int, target: dict) -> int:
    if not 0 <= index < config.shards:
        raise ValueError("shard index must be in [0, shards)")
    directory = output / f"shard-{index}"
    directory.mkdir(parents=True, exist_ok=False)
    env = {
        **os.environ,
        "SPA_E2E_SHARDS": str(config.shards),
        "SPA_E2E_SHARD_INDEX": str(index),
        "SPA_E2E_SHARD_OUTPUT": str(directory),
        "PYTEST_ADDOPTS": "",
        "PYTHONPATH": str(Path(__file__).parent)
        + os.pathsep
        + os.environ.get("PYTHONPATH", ""),
    }
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "native_e2e_plugin",
        "-n",
        str(config.workers),
        "--dist=load",
        "--max-worker-restart=0",
        "-m",
        SELECTION,
        "-x",
        "-vv",
        "--tb=short",
        "-rs",
        "-o",
        f"cache_dir={directory / 'cache'}",
        "--basetemp",
        str(directory / "tmp"),
        "--junitxml",
        str(directory / "junit.xml"),
    ]
    print(
        f"Native E2E shard {index + 1}/{config.shards}, workers={config.workers}",
        flush=True,
    )
    started = time.monotonic()
    result = subprocess.run(command, env=env, check=False)
    observed = json.loads((directory / "pytest.json").read_text())
    workers = observed["workers"]
    if (
        len(workers) != config.workers
        or not workers
        or any(w != workers[0] for w in workers)
    ):
        raise ValueError(
            "native workers did not collect the same complete suite and shard"
        )
    collection = workers[0]["collection"]
    if workers[0]["selected"] != collection[index :: config.shards]:
        raise ValueError("native worker collection does not match the planned shard")
    report = {
        "target": target,
        "shards": config.shards,
        "workers": config.workers,
        "shard_index": index,
        "selection": SELECTION,
        "exit_code": result.returncode or observed["exit_code"],
        "collection": collection,
        "outcomes": observed["outcomes"],
        "wall_seconds": round(time.monotonic() - started, 3),
    }
    path = directory / "result.json"
    path.write_text(json.dumps(report, indent=2))
    check_report(path, config, target)
    return result.returncode


def stop(children: list[subprocess.Popen]) -> None:
    running = [child for child in children if child.poll() is None]
    for child in running:
        signal_group(child, signal.SIGINT)
    deadline = time.monotonic() + 10
    for child in running:
        try:
            child.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            signal_group(child, signal.SIGKILL)
            child.wait()
        # An interrupted coordinator can exit before its workers reap native children.
        signal_group(child, signal.SIGKILL)


def signal_group(child: subprocess.Popen, value: int) -> None:
    try:
        os.killpg(child.pid, value)
    except ProcessLookupError:
        pass


def run_all(output: Path, config: Configuration, target: dict) -> int:
    output.mkdir(parents=True, exist_ok=False)
    target_path = output / "target.json"
    target_path.write_text(json.dumps(target))
    children = []
    try:
        for index in range(config.shards):
            children.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "run",
                        *config.command_args(),
                        "--shard-index",
                        str(index),
                        "--output-dir",
                        str(output),
                        "--target-file",
                        str(target_path),
                    ],
                    start_new_session=True,
                )
            )
        while any(child.poll() is None for child in children):
            failed = {
                index
                for index, child in enumerate(children)
                if child.poll() not in (None, 0)
                or (output / f"shard-{index}/failed").exists()
            }
            if failed:
                stop(
                    [
                        child
                        for index, child in enumerate(children)
                        if index not in failed
                    ]
                )
                # Keep the failing shard's traceback and in-flight fixture cleanup.
                for index in failed:
                    children[index].wait()
                return 1
            time.sleep(0.1)
        if any(child.returncode for child in children):
            return 1
        verify(output, config, target)
        return 0
    finally:
        stop(children)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify", "matrix"))
    parser.add_argument(
        "--shards",
        type=int,
        default=os.environ.get("SPA_E2E_SHARDS") or Configuration.shards,
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=os.environ.get("SPA_E2E_WORKERS") or Configuration.workers,
    )
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--target-file", type=Path)
    args = parser.parse_args()
    try:
        config = Configuration(args.shards, args.workers)
        if args.command == "matrix":
            print(
                json.dumps(
                    {
                        "include": [
                            {
                                "shard_index": index,
                                "shards": config.shards,
                                "workers": config.workers,
                            }
                            for index in range(config.shards)
                        ]
                    }
                )
            )
            return 0
        if args.output_dir is None:
            parser.error("run and verify require --output-dir")
        target = source_target(args.target_file)
        output = args.output_dir.resolve()
        if args.command == "verify":
            verify(output, config, target)
            return 0
        if args.shard_index is not None:
            return run_shard(output, config, args.shard_index, target)
        return run_all(output, config, target)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Native E2E failed: {exc}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
