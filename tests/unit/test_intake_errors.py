"""Per-file intake diagnostics for Phase 3 multi-upload."""

from __future__ import annotations

from tools.intake_errors import classify_upload_errors, format_intake_error_messages

GOOD = b"Date,Value\n2020-01-01,1\n2020-01-02,2\n"
BAD = b"not,a,valid\ncsv without enough\n"


def test_classify_reports_per_file_success_and_failure():
    results = classify_upload_errors(
        [("good.csv", GOOD), ("bad.csv", b"")]
    )
    assert len(results) == 2
    assert results[0].ok is True
    assert results[0].file_name == "good.csv"
    assert results[1].ok is False
    assert results[1].file_name == "bad.csv"
    messages = format_intake_error_messages(results)
    assert any("bad.csv" in message for message in messages)


def test_classify_flags_too_many_files():
    uploads = [(f"f{i}.csv", GOOD) for i in range(6)]
    results = classify_upload_errors(uploads)
    assert results[0].ok is False
    assert "at most 5" in (results[0].error or "")
