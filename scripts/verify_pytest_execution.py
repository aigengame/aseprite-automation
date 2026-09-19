"""Reject a missing, empty, or all-skipped pytest JUnit report."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def execution_counts(report_path: Path) -> tuple[int, int, int]:
    root = ET.parse(report_path).getroot()
    cases = root.findall(".//testcase")
    skipped = sum(case.find("skipped") is not None for case in cases)
    return len(cases), skipped, len(cases) - skipped


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_pytest_execution.py /path/to/junit.xml")

    report_path = Path(sys.argv[1])
    total, skipped, executed = execution_counts(report_path)
    print(f"JUnit execution: total={total} skipped={skipped} executed={executed}")
    if executed == 0:
        raise SystemExit("real Aseprite E2E gate executed no tests")


if __name__ == "__main__":
    main()
