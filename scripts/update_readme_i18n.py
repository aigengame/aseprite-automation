"""Record or check the English README revision used by each translation.

Adapted from godot-agent's README SHA-256 marker workflow. This records freshness,
not translation quality. Update and review all translations before stamping them.
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Check markers without changing files."
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not (root / "docs/README.zh-CN.md").is_file():
        print("Missing required translation: docs/README.zh-CN.md", file=sys.stderr)
        return 1
    source = (
        (root / "README.md").read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    )
    digest = hashlib.sha256(source).hexdigest()
    marker = f"<!-- spa-readme-i18n: source=README.md sha256={digest} -->"
    failed = False

    for path in sorted((root / "docs").glob("README.*.md")):
        body = path.read_text(encoding="utf-8")
        if args.check:
            if body.partition("\n")[0] != marker:
                print(
                    f"{path.relative_to(root)}: missing or stale README sync marker. "
                    "Update and review translations, then run "
                    "uv run python scripts/update_readme_i18n.py.",
                    file=sys.stderr,
                )
                failed = True
        else:
            body = re.sub(
                r"\A<!--\s*spa-readme-i18n:.*?-->\n*",
                "",
                body,
                count=1,
                flags=re.DOTALL,
            ).lstrip("\n")
            path.write_text(f"{marker}\n\n{body}", encoding="utf-8")
            print(f"Updated {path.relative_to(root)}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
