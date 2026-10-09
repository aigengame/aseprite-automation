"""Execute the shared native test step with controlled subprocesses and real pytest."""

import json
import os
import queue
import shutil
import subprocess
import sys
import textwrap
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / ".github/actions/run-linux-aseprite-e2e/action.yml"


def native_test_step() -> str:
    step = ACTION.read_text().split("    - name: Run real Aseprite E2E tests\n", 1)[1]
    return textwrap.dedent(step.split("      run: |\n", 1)[1].split("\n    - ", 1)[0])


@pytest.fixture
def controlled_suite(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    tools = tmp_path / "bin"
    tools.mkdir()
    uv = tools / "uv"
    uv.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "args = sys.argv[1:]\n"
        "assert args[:5] == ['run', '--frozen', '--group', 'test', 'python']\n"
        "command = [sys.executable, *args[5:]]\n"
        "os.execv(sys.executable, command)\n"
    )
    uv.chmod(0o755)
    (tmp_path / "scripts").mkdir()
    for name in ("verify_pytest_execution.py", "native_e2e.py", "native_e2e_plugin.py"):
        shutil.copy2(ROOT / "scripts" / name, tmp_path / "scripts" / name)
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-m",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    e2e: controlled native runner case\n    slow: excluded\n"
    )
    (tmp_path / "conftest.py").write_text(
        textwrap.dedent("""\
        import os
        import time
        from pathlib import Path
        import pytest
        from tests.support import fake_aseprite

        @pytest.fixture
        def policy_dir():
            return Path(os.environ["SPA_TEST_POLICY_DIR"])

        @pytest.fixture
        def wait_for():
            def wait(path):
                deadline = time.monotonic() + 15
                while not path.exists():
                    assert time.monotonic() < deadline, f"timed out waiting for {path}"
                    time.sleep(0.01)
            return wait

        @pytest.fixture
        def native_failure(tmp_path, monkeypatch):
            binary = fake_aseprite(tmp_path,
                "echo 'native stdout'\\necho 'native stderr' >&2\\nkill -TERM $$\\n")
            monkeypatch.setenv("SPA_TEST_ASEPRITE", str(binary))
            return binary
        """)
    )
    env = {
        **os.environ,
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": str(ROOT),
        "SPA_TEST_POLICY_DIR": str(tmp_path),
        "SPA_E2E_JUNIT_PATH": str(tmp_path / "spa-native-e2e/shard-0/junit.xml"),
        "SPA_E2E_SHARDS": "1",
        "SPA_E2E_WORKERS": "2",
        "SPA_E2E_SHARD_INDEX": "0",
        "SPA_NATIVE_TARGET_JSON": json.dumps({"kind": "local", "sha": sha}),
        "RUNNER_TEMP": str(tmp_path),
    }
    return tmp_path, env


def write_test(directory: Path, name: str, body: str) -> None:
    (directory / name).write_text(
        "import pytest\npytestmark = pytest.mark.e2e\n" + textwrap.dedent(body)
    )


def run_step(directory: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", native_test_step()],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_native_step_uses_the_execution_hosts_worker_configuration(controlled_suite):
    directory, env = controlled_suite
    env["SPA_E2E_WORKERS"] = "3"
    write_test(
        directory,
        "test_host_workers.py",
        "@pytest.mark.parametrize('value', range(6))\n"
        "def test_native(value):\n    assert value >= 0\n",
    )
    result = run_step(directory, env)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((directory / "spa-native-e2e/shard-0/result.json").read_text())
    assert report["workers"] == 3
    assert len(report["outcomes"]) == 6


def test_passing_negative_tests_do_not_stop_the_shared_native_step(controlled_suite):
    directory, env = controlled_suite
    write_test(
        directory,
        "test_negative.py",
        """\
        import json
        from tests.support import spa

        def test_expected_native_rejection(native_failure):
            run = spa("info", "--aseprite", str(native_failure), "--json")
            failure = json.loads(run.stdout)
            assert run.returncode == 1
            assert failure["code"] == "process_failed"
            assert "SIGTERM" in failure["message"]

        def test_after_negative(policy_dir):
            (policy_dir / "after-negative").touch()
        """,
    )
    result = run_step(directory, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (directory / "after-negative").exists()
    assert "executed=2" in result.stdout
    cases = ET.parse(env["SPA_E2E_JUNIT_PATH"]).findall(".//testcase")
    assert len(cases) == 2
    assert not any(case.find("failure") is not None for case in cases)


def test_parallel_failure_is_visible_before_inflight_work_finishes(controlled_suite):
    directory, env = controlled_suite
    write_test(
        directory,
        "test_failure.py",
        """\
        from tests.frame.test_e2e_frame import _run_fixture

        def test_native_failure(native_failure, policy_dir, wait_for):
            wait_for(policy_dir / "in-flight")
            _run_fixture("controlled.lua")

        """,
    )
    write_test(
        directory,
        "test_running.py",
        """\
        def test_in_flight(policy_dir, wait_for):
            (policy_dir / "in-flight").touch()
            wait_for(policy_dir / "release-in-flight")
            (policy_dir / "finished-in-flight").touch()
        """,
    )
    output: queue.Queue[str | None] = queue.Queue()
    output_chunks: list[str] = []
    reported_while_running = False
    with subprocess.Popen(
        ["bash", "-e", "-o", "pipefail", "-c", native_test_step()],
        cwd=directory,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) as process:
        assert process.stdout is not None

        def read_output() -> None:
            # Pytest can flush a progress result without a trailing newline.
            while chunk := process.stdout.read1(4096):
                output.put(chunk.decode("utf-8", errors="replace"))
            output.put(None)

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            while (chunk := output.get(timeout=25)) is not None:
                output_chunks.append(chunk)
                visible = "".join(output_chunks)
                if (
                    "FAILED" in visible
                    and "test_native_failure" in visible
                    and not (directory / "release-in-flight").exists()
                ):
                    reported_while_running = (
                        process.poll() is None
                        and not (directory / "finished-in-flight").exists()
                    )
                    (directory / "release-in-flight").touch()
            status = process.wait(timeout=5)
        finally:
            (directory / "release-in-flight").touch()
            if process.poll() is None:
                process.kill()
            reader.join(timeout=5)
    transcript = "".join(output_chunks)
    assert reported_while_running, transcript
    assert status != 0, transcript
    assert (directory / "finished-in-flight").exists(), transcript
    cases = ET.parse(env["SPA_E2E_JUNIT_PATH"]).findall(".//testcase")
    assert len(cases) == 2, transcript
    failures = [case.find("failure") for case in cases]
    assert sum(failure is not None for failure in failures) == 1
    for evidence in (
        transcript,
        "".join(ET.tostring(case, encoding="unicode") for case in cases),
    ):
        assert "exit status: -15" in evidence
        assert "SIGTERM" in evidence
        assert "native stdout" in evidence
        assert "native stderr" in evidence
    assert "JUnit execution:" in transcript


def test_all_skipped_native_run_still_fails_execution_audit(controlled_suite):
    directory, env = controlled_suite
    write_test(
        directory,
        "test_skipped.py",
        """\
        def test_skipped():
            pytest.skip("controlled platform exclusion")
        """,
    )
    result = run_step(directory, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert Path(env["SPA_E2E_JUNIT_PATH"]).is_file()
    assert "executed=0" in result.stdout
    result = subprocess.run(
        [
            sys.executable,
            "scripts/native_e2e.py",
            "verify",
            "--output-dir",
            str(directory / "spa-native-e2e"),
            "--target-file",
            str(directory / "spa-native-target.json"),
        ],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert "executed no tests" in result.stderr


@pytest.mark.parametrize(("choice", "failures"), [((), 1), (("--maxfail=0",), 2)])
def test_local_full_failure_collection_is_an_explicit_choice(
    controlled_suite, choice: tuple[str, ...], failures: int
):
    directory, env = controlled_suite
    write_test(
        directory,
        "test_failures.py",
        """\
        @pytest.mark.parametrize("number", range(2))
        def test_failure(number):
            assert False, f"controlled failure {number}"
        """,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-x",
            "-vv",
            "--tb=short",
            *choice,
            f"--junitxml={env['SPA_E2E_JUNIT_PATH']}",
        ],
        cwd=directory,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    cases = ET.parse(env["SPA_E2E_JUNIT_PATH"]).findall(".//testcase")
    assert len(cases) == failures
    assert all(case.find("failure") is not None for case in cases)
