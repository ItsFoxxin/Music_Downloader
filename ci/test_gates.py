"""The release skip guard must reject missing, failed or silently skipped tests."""
import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize("body,passes", [
    ('<testcase name="test_audio"/>', True),
    ('<testcase name="test_windows_import_lock_initializes_once_under_lock"><skipped/></testcase>', True),
    ('<testcase name="test_archive_symlink"><skipped/></testcase>', False),
    ('<testcase name="test_audio"><failure/></testcase>', False),
    ('<testcase name="test_audio"><error/></testcase>', False),
    ('', False),
])
def test_release_report_guard(tmp_path, body, passes):
    script = Path(__file__).with_name("check_test_report.py")
    validate = runpy.run_path(str(script))["validate"]
    report = tmp_path / "junit.xml"
    report.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>")
    if passes:
        validate(report)
    else:
        with pytest.raises(AssertionError):
            validate(report)
