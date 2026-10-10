"""README freshness is enforced by the same check locally and in Fast tests."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_sync(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "scripts/update_readme_i18n.py"), *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@pytest.fixture
def readme_repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts/update_readme_i18n.py", tmp_path / "scripts")
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("# SPA\n\nInstall SPA.\n", encoding="utf-8")
    (tmp_path / "docs/README.zh-CN.md").write_text(
        "# SPA\n\n安装 SPA。\n", encoding="utf-8"
    )
    return tmp_path


def test_editing_english_requires_translation_sync(readme_repo: Path) -> None:
    assert run_sync(readme_repo).returncode == 0
    assert run_sync(readme_repo, "--check").returncode == 0

    (readme_repo / "README.md").write_text(
        "# SPA\n\nInstall SPA and its Skill.\n", encoding="utf-8"
    )
    translation = readme_repo / "docs/README.zh-CN.md"
    original = translation.read_bytes()
    result = run_sync(readme_repo, "--check")
    assert result.returncode == 1
    assert "docs/README.zh-CN.md" in result.stderr
    assert translation.read_bytes() == original

    translation.write_text("# SPA\n\n安装 SPA 及其 Skill。\n", encoding="utf-8")
    assert run_sync(readme_repo).returncode == 0
    assert run_sync(readme_repo, "--check").returncode == 0


@pytest.mark.parametrize("args", [(), ("--check",)])
def test_missing_chinese_readme_fails(readme_repo: Path, args: tuple[str, ...]) -> None:
    (readme_repo / "docs/README.zh-CN.md").unlink()
    result = run_sync(readme_repo, *args)
    assert result.returncode == 1
    assert "docs/README.zh-CN.md" in result.stderr


def test_repository_translations_match_english() -> None:
    result = run_sync(ROOT, "--check")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("placement", ["missing", "below-heading", "invalid"])
def test_check_requires_a_valid_leading_marker(
    readme_repo: Path, placement: str
) -> None:
    assert run_sync(readme_repo).returncode == 0
    translation = readme_repo / "docs/README.zh-CN.md"
    marker, _, body = translation.read_text(encoding="utf-8").partition("\n\n")
    changed = {
        "missing": body,
        "below-heading": f"# Translation\n\n{marker}\n\n{body}",
        "invalid": f"{marker.replace('sha256=', 'sha256=invalid')}\n\n{body}",
    }[placement]
    translation.write_text(changed, encoding="utf-8")
    result = run_sync(readme_repo, "--check")
    assert result.returncode == 1
    assert "docs/README.zh-CN.md" in result.stderr


def test_additional_locales_are_checked_without_configuration(
    readme_repo: Path,
) -> None:
    assert run_sync(readme_repo).returncode == 0
    (readme_repo / "docs/README.fr.md").write_text(
        "# Installer SPA\n", encoding="utf-8"
    )
    result = run_sync(readme_repo, "--check")
    assert result.returncode == 1
    assert "docs/README.fr.md" in result.stderr
    assert run_sync(readme_repo).returncode == 0
    assert run_sync(readme_repo, "--check").returncode == 0


@pytest.mark.parametrize("newline", [b"\r\n", b"\r"])
def test_line_endings_do_not_invalidate_translations(
    readme_repo: Path, newline: bytes
) -> None:
    assert run_sync(readme_repo).returncode == 0
    for name in ("README.md", "docs/README.zh-CN.md"):
        path = readme_repo / name
        path.write_bytes(path.read_bytes().replace(b"\n", newline))
    assert run_sync(readme_repo, "--check").returncode == 0


def test_stamping_preserves_prose_and_is_idempotent(readme_repo: Path) -> None:
    translation = readme_repo / "docs/README.zh-CN.md"
    original = translation.read_bytes()
    assert run_sync(readme_repo).returncode == 0
    stamped = translation.read_bytes()
    assert stamped.split(b"\n\n", maxsplit=1)[1] == original
    assert run_sync(readme_repo).returncode == 0
    assert translation.read_bytes() == stamped
