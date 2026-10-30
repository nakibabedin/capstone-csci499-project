"""Find the date a lab report's sample was taken, from its text lines.

Looks for a labelled date ("Date Collected: 01/21/2025", "Reported On 21-Jan-2025")
and prefers, in order: collection date, report date, received/registration date,
then any line labelled "Date". Dates of birth and previous results are ignored.

Returns {"label", "text", "iso"} or None. `text` is the date as printed; `iso`
is YYYY-MM-DD, or None when day and month can't be told apart (03/04/2025).
"""

import re
from datetime import date

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)[a-z]*\.?"
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

DATE_PATTERNS = [
    ("ymd", re.compile(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b")),
    ("num", re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})\b")),
    ("d_mon_y", re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?[\s/-]+({_MONTH})[\s/,-]+(\d{{4}}|\d{{2}})\b", re.I)),
    ("mon_d_y", re.compile(rf"\b({_MONTH})[\s/-]+(\d{{1,2}})(?:st|nd|rd|th)?,?[\s/-]+(\d{{4}})\b", re.I)),
]

# Most preferred first.
LABELS = [
    # "Sample"/"Report" alone are often titles ("Sample Report"), so they need a
    # word like "date" or "on" after them.
    ("Collected", re.compile(
        r"\b(?:collect\w*|drawn)\b|\b(?:sampl\w*|specimen)\s+(?:date|time|on|taken|collect\w*)\b", re.I)),
    ("Reported", re.compile(r"\breported\b|\breport\s+(?:date|time|on)\b", re.I)),
    ("Received", re.compile(r"\b(?:receiv\w*|regist\w*)\b", re.I)),
    ("Date", re.compile(r"\bdate\b", re.I)),
]
SKIP_RE = re.compile(r"birth|\bdob\b|previous|prior|print", re.I)
# How far after its label a date may start ("Date Collected:  On 01/21/2025").
MAX_LABEL_GAP = 20
# A label that ends its line ("Registered on"), so the date may start the next one.
LABEL_END_RE = re.compile(r"^[\s:.-]*(?:on|at|date|time)?[\s:.-]*$", re.I)


def _year(text):
    y = int(text)
    if len(text) == 2:
        y += 2000 if y < 70 else 1900
    return y


def _iso(y, m, d):
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_date(text):
    """The first date in `text` as (matched text, iso or None, start index), or None."""
    found = []
    for kind, pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            found.append((match.start(), kind, match))
    if not found:
        return None
    start, kind, match = min(found, key=lambda f: f[0])
    a, b, c = match.groups()

    if kind == "ymd":
        iso = _iso(int(a), int(b), int(c))
    elif kind == "d_mon_y":
        iso = _iso(_year(c), MONTHS[b[:3].lower()], int(a))
    elif kind == "mon_d_y":
        iso = _iso(_year(c), MONTHS[a[:3].lower()], int(b))
    else:
        first, second, y = int(a), int(b), _year(c)
        if first > 12 >= second:
            iso = _iso(y, second, first)  # day/month
        elif second > 12 >= first:
            iso = _iso(y, first, second)  # month/day
        else:
            iso = None  # ambiguous, e.g. 03/04/2025
    return match.group(0), iso, start


def find_report_date(lines):
    best = None  # (priority, label, text, iso)
    for i, line in enumerate(lines):
        if SKIP_RE.search(line):
            continue
        for priority, (label, pattern) in enumerate(LABELS):
            if best is not None and priority >= best[0]:
                break
            match = pattern.search(line)
            if not match:
                continue
            # The date follows its label on the same line, or starts the next line.
            parsed = parse_date(line[match.end():])
            if parsed is not None and parsed[2] > MAX_LABEL_GAP:
                parsed = None
            if parsed is None and LABEL_END_RE.match(line[match.end():]) and i + 1 < len(lines):
                nxt = parse_date(lines[i + 1])
                if nxt is not None and nxt[2] == 0:
                    parsed = nxt
            if parsed is not None:
                best = (priority, label, parsed[0], parsed[1])
                break
        if best is not None and best[0] == 0:
            break
    if best is None:
        return None
    return {"label": best[1], "text": best[2], "iso": best[3]}
