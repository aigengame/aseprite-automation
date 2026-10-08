"""Execute release-tail guards and recovery with controlled external tools."""

import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tarfile
import textwrap
import zipfile
from pathlib import Path

import pytest

from scripts.release_distributions import verify_pypi

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/release.yml"


def run_step(name: str, directory: Path, environment: dict[str, str]):
    step = WORKFLOW.read_text().split(f"      - name: {name}\n", 1)[1]
    body = re.split(
        r"\n(?=\S| {1,8}\S)", step.split("        run: |\n", 1)[1], maxsplit=1
    )[0]
    return subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", textwrap.dedent(body)],
        cwd=directory,
        env={**os.environ, **environment},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def publish_environment() -> dict[str, str]:
    return {
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "push",
        "SPA_CUT_RESULT": "success",
        "SPA_VERIFY_RESULT": "success",
        "SPA_PYPI_RESULT": "success",
        "SPA_RELEASE_CREATED": "true",
        "SPA_RELEASE_TAG": "v1.2.3",
        "SPA_RELEASE_SHA": "a" * 40,
    }


@pytest.mark.parametrize("failure", ["failure", "cancelled", "skipped"])
def test_pypi_failure_keeps_github_publication_in_failed_tail(
    tmp_path: Path, failure: str
) -> None:
    environment = publish_environment() | {"SPA_PYPI_RESULT": failure}
    result = run_step(
        "Require successful draft and verification jobs", tmp_path, environment
    )
    assert result.returncode != 0
    assert "Re-run failed jobs" in result.stderr


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("SPA_VERIFY_RESULT", "failure"),
        ("SPA_VERIFY_RESULT", "skipped"),
        ("SPA_CUT_RESULT", "failure"),
        ("SPA_RELEASE_CREATED", "false"),
        ("GITHUB_EVENT_NAME", "workflow_dispatch"),
        ("GITHUB_EVENT_NAME", "pull_request"),
        ("GITHUB_REF", "refs/heads/dev"),
        ("SPA_RELEASE_SHA", ""),
        ("SPA_RELEASE_TAG", ""),
    ],
)
def test_upload_requires_an_approved_exact_release(
    tmp_path: Path, key: str, value: str
) -> None:
    result = run_step(
        "Require an approved and verified release",
        tmp_path,
        publish_environment() | {key: value},
    )
    assert result.returncode != 0


def test_approved_release_can_publish(tmp_path: Path) -> None:
    result = run_step(
        "Require an approved and verified release", tmp_path, publish_environment()
    )
    assert result.returncode == 0, result.stderr


def test_attestations_do_not_contaminate_the_verified_release_pair(
    tmp_path: Path, monkeypatch
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    prefix = "aseprite_automation-1.2.3"
    metadata = b"Name: aseprite-automation\nVersion: 1.2.3\n"
    with zipfile.ZipFile(dist / f"{prefix}-py3-none-any.whl", "w") as wheel:
        wheel.writestr(f"{prefix}.dist-info/METADATA", metadata)
    with tarfile.open(dist / f"{prefix}.tar.gz", "w:gz") as sdist:
        member = tarfile.TarInfo(f"{prefix}/PKG-INFO")
        member.size = len(metadata)
        sdist.addfile(member, io.BytesIO(metadata))
    original = {path.name: path.read_bytes() for path in dist.iterdir()}
    remote_files = []
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **kw: io.BytesIO(
            json.dumps(
                {
                    "info": {"name": "aseprite-automation", "version": "1.2.3"},
                    "urls": remote_files,
                }
            ).encode()
        ),
    )

    job = (
        WORKFLOW.read_text()
        .split("\n  publish-pypi:\n", 1)[1]
        .split("\n  publish:\n", 1)[0]
    )
    for step in job.split("      - name: ")[1:]:
        if "run: python3 -I scripts/release_distributions.py" in step:
            command = shlex.split(step.split("run: ", 1)[1].strip())
            verify_pypi(
                tmp_path / command[3],
                "1.2.3",
                allow_missing="--allow-missing" in command,
            )
        elif "run: |" in step:
            result = run_step(step.splitlines()[0], tmp_path, publish_environment())
            assert result.returncode == 0, result.stderr
        elif "uses: pypa/gh-action-pypi-publish@" in step:
            upload_dir = tmp_path / step.split("packages-dir: ", 1)[1].splitlines()[0]
            assert {p.name: p.read_bytes() for p in upload_dir.iterdir()} == original
            # The pinned PyPA action writes these sidecars next to the uploads.
            for path in list(upload_dir.iterdir()):
                remote_files.append(
                    {
                        "filename": path.name,
                        "size": path.stat().st_size,
                        "digests": {
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                        },
                    }
                )
                path.with_name(path.name + ".publish.attestation").write_text("{}")

    assert len(remote_files) == 2
    assert {path.name: path.read_bytes() for path in dist.iterdir()} == original


def test_github_failure_after_pypi_success_resumes_the_same_files(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "aseprite_automation-1.2.3-py3-none-any.whl").write_bytes(b"verified wheel")
    (dist / "aseprite_automation-1.2.3.tar.gz").write_bytes(b"verified sdist")
    tools = tmp_path / "bin"
    tools.mkdir()
    gh = tools / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        + textwrap.dedent("""\
        import json, os, sys
        from pathlib import Path
        args = sys.argv[1:]
        with Path('calls.jsonl').open('a') as log:
            log.write(json.dumps(args) + '\\n')
        if args[:2] == ['release', 'upload']:
            assert '--clobber' in args
            for name in args[3:5]:
                assert Path(name).read_bytes().startswith(b'verified ')
        elif args[:2] == ['release', 'edit']:
            if not Path('failed-once').exists():
                Path('failed-once').touch()
                sys.exit(1)
            Path('published').touch()
        else:
            sys.exit(2)
    """)
    )
    gh.chmod(0o755)
    environment = publish_environment() | {
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_REPOSITORY": "example/spa",
    }
    original = {p.name: p.read_bytes() for p in dist.iterdir()}
    assert (
        run_step(
            "Require successful draft and verification jobs", tmp_path, environment
        ).returncode
        == 0
    )
    failed = run_step("Attach assets and publish the draft", tmp_path, environment)
    assert failed.returncode != 0
    assert not (tmp_path / "published").exists()
    retried = run_step("Attach assets and publish the draft", tmp_path, environment)
    assert retried.returncode == 0, retried.stderr
    assert (tmp_path / "published").exists()
    assert {p.name: p.read_bytes() for p in dist.iterdir()} == original
    calls = [
        json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()
    ]
    assert calls[:2] == calls[2:]
