"""Fail closed if Linux CI silently skips safety or integration tests."""
import sys
import xml.etree.ElementTree as ET

ALLOWED_SKIPS = {
    "test_windows_import_lock_initializes_once_under_lock",
    "test_windows_import_lock_fails_closed_without_rewriting_an_unknown_file",
}


def validate(path):
    cases = list(ET.parse(path).iter("testcase"))
    assert cases, "No test cases were collected"
    failed = [case.attrib["name"] for case in cases if case.find("failure") is not None or case.find("error") is not None]
    skipped = [case.attrib["name"] for case in cases if case.find("skipped") is not None]
    assert not failed, f"Failed tests: {failed}"
    assert set(skipped) <= ALLOWED_SKIPS, f"Unexpected skipped tests: {skipped}"
    print(f"Validated {len(cases)} tests; allowed platform skips: {skipped}")


if __name__ == "__main__":
    validate(sys.argv[1])
