"""Validate version metadata; stable promotions also require a version increase."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="Git SHA of the stable branch before promotion")
    parser.add_argument("--reports", nargs="*", help="JUnit reports that must have no failures or skips")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    version = (root / "VERSION").read_text().strip()
    assert re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version), "VERSION must be MAJOR.MINOR.PATCH"
    assert f"fox-den-media:{version}" in (root / "compose.yaml").read_text(), "Compose image version differs"
    assert f"**{version}**" in (root / "README.md").read_text(encoding="utf-8"), "README version differs"
    assert re.search(rf"^## {re.escape(version)} - \d{{4}}-\d{{2}}-\d{{2}}$", (root / "CHANGELOG.md").read_text(), re.M), "Missing dated changelog entry"
    assert "COPY VERSION ./VERSION" in (root / "Dockerfile").read_text(), "Media image must contain VERSION"
    if args.base and set(args.base) != {"0"}:
        # Verify the commit exists; only a missing VERSION file is treated as 0.0.0.
        subprocess.run(["git", "cat-file", "-e", args.base + "^{commit}"], cwd=root, check=True)
        listing = subprocess.check_output(["git", "ls-tree", "--name-only", args.base, "VERSION"], cwd=root, text=True)
        previous = subprocess.check_output(["git", "show", args.base + ":VERSION"], cwd=root, text=True).strip() if listing.strip() else "0.0.0"
        assert tuple(map(int, version.split('.'))) > tuple(map(int, previous.split('.'))), "Stable promotion requires a version increase"
    for report in args.reports or []:
        cases = ET.parse(report).findall('.//testcase')
        assert cases, f"No test cases in {report}"
        windows_only = {
            "test_windows_import_lock_initializes_once_under_lock": "Windows marker initialization is platform-specific",
            "test_windows_import_lock_fails_closed_without_rewriting_an_unknown_file": "Windows marker validation is platform-specific",
        }
        for case in cases:
            assert case.find("failure") is None and case.find("error") is None, f"Stable test failed: {report}"
            skipped = case.find("skipped")
            if skipped is not None:
                allowed = (sys.platform.startswith("linux") and case.get("classname", "").endswith("test_library")
                           and case.get("name") in windows_only
                           and skipped.get("message") == windows_only[case.get("name")])
                assert allowed, f"Unexpected skipped stable test: {case.get('name')} in {report}"
    print(f"Release metadata passed: {version}")


if __name__ == "__main__":
    main()
