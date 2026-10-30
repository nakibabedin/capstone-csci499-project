import pytest

from report_date import find_report_date


@pytest.mark.parametrize("lines, expected", [
    (["Date Collected: 01/21/2025 Date Reported: 01/22/2025"], ("Collected", "01/21/2025", "2025-01-21")),
    (["Reported: 2025-03-04", "Collected On: 21-Jan-2025 10:30"], ("Collected", "21-Jan-2025", "2025-01-21")),
    (["Report Date Jan 5, 2024"], ("Reported", "Jan 5, 2024", "2024-01-05")),
    (["Registered on", "12th March 2024"], ("Received", "12th March 2024", "2024-03-12")),
    (["Sample Date: 21/03/2025"], ("Collected", "21/03/2025", "2025-03-21")),
    # Day and month can't be told apart, so only the printed text is kept.
    (["Sample Date: 03/04/2025"], ("Collected", "03/04/2025", None)),
])
def test_finds_labelled_date(lines, expected):
    found = find_report_date(lines)
    assert (found["label"], found["text"], found["iso"]) == expected


@pytest.mark.parametrize("lines", [
    ["Date of Birth: 01/02/1980"],
    ["DOB 05/06/1990"],
    ["Previous Result and Date 01/01/2024"],
    # A title, not a label: "Sample Report" is followed by a date of birth here.
    ["Sample Report, 505271 01/01/1970 Patient Report"],
    ["Hemoglobin 13.5 g/dL 12.0 - 15.5"],
])
def test_ignores_unlabelled_or_other_dates(lines):
    assert find_report_date(lines) is None
