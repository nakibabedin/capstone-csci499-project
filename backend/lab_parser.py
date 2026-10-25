"""Fast, rule-based parsing of blood test report PDFs.

Text is pulled out with PyMuPDF and rebuilt into visual lines from span
coordinates, skipping text a reader can't see (hidden watermarks) and small
print under a test name (the test method). Each line is then matched against
the shape of a result row:

    <test name>  [flag]  <value>[flag]  [flag]  [unit]  [reference range]

where the unit and reference range may come in either order. A line only
counts as a result if its value is followed by a unit or a reference range,
which keeps page headers, addresses and phone numbers out of the results.

Rows whose result is a word ("HBsAg Non Reactive", "Urine Ketone Absent Absent")
are only accepted for tests that list that word among their answers (see
biomarkers.py), for the same reason.
"""

import re
from collections import Counter

import pymupdf

from biomarkers import BIOMARKERS, normalize_answer
from analysis import available_analyses
from panels import derive, detect_panels, enrich, review_list

# Text whose vertical centers are within this many points shares a line.
LINE_TOLERANCE = 3.0
# Text smaller than this fraction of a line's main font size is dropped from it
# (e.g. the test method printed in small type under the test name).
SMALL_PRINT_RATIO = 0.8

NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"
VALUE_RE = re.compile(rf"^(?P<cmp>[<>]=?)?(?P<num>{NUMBER})(?P<flag>HH|LL|H|L|A|\*)?$")
RANGE_RE = re.compile(
    rf"^(?P<low>{NUMBER})-(?P<high>{NUMBER})$|^(?P<cmp>[<>]=?|≤|≥)(?P<bound>{NUMBER})$"
)
DATE_RE = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$")
# Cells per microscope field: "3" or "1-2".
COUNT_RE = re.compile(r"^(\d+)(?:-(\d+))?$")
# The longest test name the word-answer pass tries ("HIV I & II Ab/Ag with P24 Ag").
MAX_NAME_TOKENS = 8
# "12.0 - 16.0" -> "12.0-16.0" and "< 100" -> "<100" so each range is one token.
SPACED_RANGE_RE = re.compile(rf"({NUMBER})\s*[-–]\s*({NUMBER})")
SPACED_BOUND_RE = re.compile(r"([<>]=?|≤|≥)\s+(?=[\d.])")
# "Up to 5.0" -> "<=5.0"
UP_TO_RE = re.compile(r"\bup to\s+(?=[\d.])", re.IGNORECASE)
# "micro g/dL" -> "microg/dL" so the unit is one token.
SPLIT_UNIT_RE = re.compile(r"\b(micro|milli|nano|pico)\s+(?=\S*/)", re.IGNORECASE)

FLAGS = {
    "H": "H", "HIGH": "H", "HH": "HH",
    "L": "L", "LOW": "L", "LL": "LL",
    "A": "A", "ABN": "A", "ABNORMAL": "A",
    "CRIT": "critical", "CRITICAL": "critical",
    "*": "*",
}
# Flags some labs print between the test name and the value.
LEADING_FLAGS = {"H", "HH", "L", "LL", "HIGH", "LOW"}
UNIT_WORDS = {"%", "fl", "pg", "g", "sec", "secs", "seconds", "mmhg", "units", "iu", "u", "index", "coi"}

# Lines whose "name" starts with one of these are patient/lab metadata, not results.
METADATA_WORDS = {
    "page", "phone", "tel", "fax", "age", "dob", "account", "acct", "npi", "id",
    "specimen", "patient", "physician", "doctor", "ordered", "collected",
    "received", "reported", "suite", "zip", "lab", "clia", "control", "requisition",
}
SECTION_RE = re.compile(
    r"\b(panel|profile|count|chemistry|hematology|lipids?|urinalysis|thyroid|"
    r"differential|metabolic|electrolytes|vitamins?|iron|hormones?)\b",
    re.IGNORECASE,
)
# Labels that mark a range as the normal range. Other labelled ranges
# ("Low: <40.0", "Borderline High: 200-239", "Deficiency: <10") are tiers of an
# interpretation table, not the normal range, so they're ignored.
NORMAL_RANGE_LABELS = {
    "normal", "desirable", "optimal", "reference", "ref", "range", "adult", "adults",
    "negative", "non reactive", "nonreactive",
}
PAGE_NUMBER_RE = re.compile(r"^page \d+( of \d+)?$", re.IGNORECASE)
COLUMN_HEADER_WORDS = {"test", "result", "results", "flag", "units", "reference", "range", "interval"}

# Patient age and sex as report headers print them:
# "Sex/Age : Male / 41 Y", "Age/Sex: 41 Yrs / F", "Age : 41 Years", "Gender : Female".
SEX = r"(?P<sex>male|female|m|f)\b"
AGE = r"(?P<age>\d{1,3}(?:\.\d+)?)\s*(?P<age_unit>y|yrs?|years?|m|mths?|months?|d|days?)?\b"
PATIENT_PATTERNS = [
    re.compile(rf"\b(?:sex|gender)\s*/\s*age\s*:?\s*{SEX}\s*/\s*{AGE}", re.IGNORECASE),
    re.compile(rf"\bage\s*/\s*(?:sex|gender)\s*:?\s*{AGE}\s*/\s*{SEX}", re.IGNORECASE),
    re.compile(rf"\bage\s*(?:\(\s*years?\s*\))?\s*:\s*{AGE}", re.IGNORECASE),
    re.compile(rf"\b(?:sex|gender)\s*:\s*{SEX}", re.IGNORECASE),
]
AGE_UNIT_YEARS = {"m": 1 / 12, "mth": 1 / 12, "mths": 1 / 12, "month": 1 / 12, "months": 1 / 12, "d": 1 / 365, "day": 1 / 365, "days": 1 / 365}


def _normalize_name(name):
    return " ".join(re.sub(r"[^a-z0-9%]+", " ", name.lower()).split())


def _strip_qualifiers(key):
    key = re.sub(r"\b(serum|plasma|blood|whole|calc)\b", " ", key)
    return " ".join(key.split())


# Normalized spelling -> canonical name. Matching is exact on purpose (see biomarkers.py).
ALIASES = {
    _normalize_name(alias): canonical
    for canonical, biomarker in BIOMARKERS.items()
    for alias in biomarker["aliases"] + [canonical]
}


def canonical_name(name):
    key = _normalize_name(name)
    if key in ALIASES:
        return ALIASES[key]
    without_parens = _normalize_name(re.sub(r"\(.*?\)", " ", name))
    for candidate in (without_parens, _strip_qualifiers(key), _strip_qualifiers(without_parens)):
        if candidate in ALIASES:
            return ALIASES[candidate]
    return None


def _to_float(text):
    return float(text.replace(",", ""))


def _is_unit(token):
    if DATE_RE.match(token):
        return False
    return "/" in token or token.lower() in UNIT_WORDS


def _is_filler(token):
    """Tokens that may sit between a value and its unit/range (flags, previous results, dates)."""
    return (
        token.upper() in FLAGS
        or VALUE_RE.match(token) is not None
        or DATE_RE.match(token) is not None
    )


def _range_is_labelled_tier(tokens, j):
    """True if the range at tokens[j] has a label other than a normal-range label."""
    if j == 0 or not tokens[j - 1].endswith(":"):
        return False
    words = [t.rstrip(":").lower() for t in tokens[max(0, j - 3):j] if t != ":"]
    return not ({" ".join(words[-1:]), " ".join(words[-2:])} & NORMAL_RANGE_LABELS)


def _looks_like_prose(tokens):
    """Explanatory notes that happen to contain a value and a unit."""
    first = tokens[0]
    return (
        len(tokens) > 10
        or first[0] in "•◦▪*-–("
        or tokens[-1].endswith("=")
        or (first[0].islower() and len(tokens) > 2)
    )


def _clean_line(line):
    line = SPLIT_UNIT_RE.sub(r"\1", UP_TO_RE.sub("<=", line))
    return SPACED_BOUND_RE.sub(r"\1", SPACED_RANGE_RE.sub(r"\1-\2", line))


def parse_result_line(line):
    """Parse one text line into a list of result dicts (empty if it isn't a result row).

    Numeric rows are tried first; a row whose result is a word ("Non Reactive")
    is only accepted for a test that lists that word among its answers.
    """
    line = _clean_line(line)
    return _parse_numeric_line(line) or _parse_answer_line(line)


def _match_answer(tokens, answers, allow_count):
    """(text, token count) of the longest known answer starting tokens, or None.

    Urine microscopy reports cells per field as a count or range ("1-2"), which
    `allow_count` accepts as well.
    """
    for n in range(min(4, len(tokens)), 0, -1):
        text = " ".join(tokens[:n])
        if normalize_answer(text) in answers:
            return text, n
    if allow_count and tokens and COUNT_RE.match(tokens[0]):
        return tokens[0], 1
    return None


def _parse_answer_line(line):
    """A row whose result is a word: "Rh (D) Type Positive", "Urine Glucose Present (+) Absent".

    The name must resolve to a test with `answers` and the value must be one of
    them, so a sentence that merely contains "negative" can't become a result.
    After the value only a unit and a reference (an answer or a range) may follow.
    """
    tokens = [t for t in line.split() if t != ":"]
    if len(tokens) < 2 or _looks_like_prose(tokens):
        return []
    for k in range(1, min(MAX_NAME_TOKENS, len(tokens) - 1) + 1):
        name = " ".join(tokens[:k]).strip(" :.-")
        canonical = canonical_name(name)
        biomarker = BIOMARKERS.get(canonical)
        if biomarker is None or not biomarker["answers"]:
            continue
        allow_count = biomarker["unit"] == "/hpf"
        value = _match_answer(tokens[k:], biomarker["answers"], allow_count)
        if value is None:
            continue
        value_text, n = value
        rest = tokens[k + n:]
        unit = rest.pop(0) if rest and _is_unit(rest[0]) else None

        reference_range = ref_low = ref_high = None
        ref = RANGE_RE.match(rest[0]) if len(rest) == 1 else None
        if ref and ref["low"] is not None:
            reference_range, ref_low, ref_high = ref.group(0), _to_float(ref["low"]), _to_float(ref["high"])
        elif ref:
            reference_range = ref.group(0)
            if ref["cmp"] in ("<", "<=", "≤"):
                ref_high = _to_float(ref["bound"])
            else:
                ref_low = _to_float(ref["bound"])
        elif rest and rest != ["."]:
            ref_answer = _match_answer(rest, biomarker["answers"], allow_count)
            if ref_answer is None or ref_answer[1] != len(rest):
                continue  # something else follows the value; not a result row
            reference_range = ref_answer[0]

        count = COUNT_RE.match(value_text)
        return [{
            "test": name,
            "canonical": canonical,
            # A count range ("1-2" cells) is compared by its upper end.
            "value": _to_float(count[2] or count[1]) if count else None,
            "value_text": value_text,
            "unit": unit,
            "flag": None,
            "reference_range": reference_range,
            "ref_low": ref_low,
            "ref_high": ref_high,
        }]
    return []


def _parse_numeric_line(line):
    """A row whose result is a number.

    A line holds two results when a differential count prints the percentage and
    the absolute count side by side: "Neutrophils 73 % 40-80 7716 /cmm 2000-6700".
    """
    tokens = line.split()

    for i in range(1, len(tokens)):
        value = VALUE_RE.match(tokens[i])
        if not value:
            continue
        # The value must be followed, past any flags/previous results, by a unit or range.
        rest = tokens[i + 1:]
        anchor = next((t for t in rest if not _is_filler(t) or RANGE_RE.match(t)), None)
        if anchor is None or not (_is_unit(anchor) or RANGE_RE.match(anchor)):
            continue

        name_tokens = tokens[:i]
        flag = FLAGS.get(value["flag"]) if value["flag"] else None
        # Some labs print the flag in its own column before the value.
        while len(name_tokens) > 1 and name_tokens[-1].upper() in LEADING_FLAGS:
            flag = flag or FLAGS[name_tokens.pop().upper()]
        name = " ".join(name_tokens).strip(" :.-")
        if not re.search(r"[A-Za-z]", name) or len(name) > 60 or _looks_like_prose(name_tokens):
            return []
        if _normalize_name(name).split(" ")[0] in METADATA_WORDS:
            return []

        unit = ref = None
        end = len(rest)
        for j, token in enumerate(rest):
            is_range = RANGE_RE.match(token)
            if is_range:
                if ref is None and not _range_is_labelled_tier(tokens, i + 1 + j):
                    ref = is_range
            elif VALUE_RE.match(token) and (unit or ref):
                end = j  # the start of a second result on the same line
                break
            elif unit is None and _is_unit(token):
                unit = token
            elif flag is None and token.upper() in FLAGS:
                flag = FLAGS[token.upper()]

        # "<0.5" or ">7.0" with no reference range is usually a row of an
        # interpretation table ("Poor Control: >7.0 %"), not a result.
        if value["cmp"] and ref is None:
            return []

        ref_low = ref_high = None
        if ref is not None:
            if ref["low"] is not None:
                ref_low, ref_high = _to_float(ref["low"]), _to_float(ref["high"])
            elif ref["cmp"] in ("<", "<=", "≤"):
                ref_high = _to_float(ref["bound"])
            else:
                ref_low = _to_float(ref["bound"])

        results = [{
            "test": name,
            "canonical": canonical_name(name),
            "value": _to_float(value["num"]),
            "value_text": (value["cmp"] or "") + value["num"],
            "unit": unit,
            "flag": flag,
            "reference_range": ref.group(0) if ref else None,
            "ref_low": ref_low,
            "ref_high": ref_high,
        }]
        remainder = rest[end:]
        if unit == "%" and remainder:
            absolute = parse_result_line(f"{name} (Absolute) " + " ".join(remainder))
            results += [r for r in absolute if r["unit"] != "%"][:1]
        return results
    return []


def _is_section_header(line):
    if re.search(r"\d", line) or len(line) > 60 or not re.search(r"[A-Za-z]", line):
        return False
    words = set(_normalize_name(line).split())
    if len(words & COLUMN_HEADER_WORDS) >= 2:
        return False
    return line.isupper() or SECTION_RE.search(line) is not None


def _body_size(spans):
    """The font size of a line's main text: its largest text containing a digit
    (values, units, ranges), falling back to the size most characters use."""
    numeric = [size for _, _, size, text in spans if re.search(r"\d", text)]
    if numeric:
        return max(numeric)
    sizes = sorted(size for _, _, size, text in spans for _ in text)
    return sizes[len(sizes) // 2]


def _page_lines(page):
    """Rebuild visual lines (left-to-right, top-to-bottom) from text span positions.

    Text a reader can't see is skipped: white, tiny, rotated or off the page.
    PDFs often carry such text as watermarks or hidden IDs, and it would
    otherwise get merged into test names.
    """
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for pdf_line in block.get("lines", []):
            if abs(pdf_line["dir"][1]) > 0.01:
                continue
            for span in pdf_line["spans"]:
                x0, y0, x1, y1 = span["bbox"]
                text = span["text"].strip()
                if (
                    not text
                    or span["size"] < 3
                    or span["color"] == 0xFFFFFF
                    or x1 <= page.rect.x0
                    or x0 >= page.rect.x1
                ):
                    continue
                spans.append((x0, (y0 + y1) / 2, span["size"], text))

    spans.sort(key=lambda s: (s[1], s[0]))
    rows, current, row_y = [], [], None
    for span in spans:
        if current and span[1] - row_y > LINE_TOLERANCE:
            rows.append(current)
            current = []
        if not current:
            row_y = span[1]
        current.append(span)
    if current:
        rows.append(current)

    lines = []
    for row in rows:
        min_size = SMALL_PRINT_RATIO * _body_size(row)
        kept = sorted((s for s in row if s[2] >= min_size), key=lambda s: s[0])
        lines.append(" ".join(s[3] for s in kept))
    return lines


def extract_patient(pages):
    """The patient's age (years) and sex from the report header, each None if not printed.

    Searches the raw page lines, since headers repeat on every page and are
    dropped as boilerplate before results are parsed.
    """
    patient = {"age": None, "sex": None, "source": None}
    for line in (line for lines in pages for line in lines):
        for pattern in PATIENT_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            groups = match.groupdict()
            if patient["sex"] is None and groups.get("sex"):
                patient["sex"] = "male" if groups["sex"].lower().startswith("m") else "female"
                patient["source"] = patient["source"] or line
            if patient["age"] is None and groups.get("age"):
                age = float(groups["age"]) * AGE_UNIT_YEARS.get((groups.get("age_unit") or "y").lower(), 1)
                if 0 <= age <= 120:
                    patient["age"] = round(age, 1) if age < 2 else int(age)
                    patient["source"] = patient["source"] or line
        if patient["age"] is not None and patient["sex"] is not None:
            break
    return patient


def parse_lab_report(contents, max_pages):
    """Parse a PDF's bytes into lab results.

    Returns (report, num_pages), where report holds:
      results   - parsed results, enriched with canonical-unit values (see panels.py),
                  plus derived results marked `derived`
      panels    - the test panels detected, with their missing tests
      biomarkers - the detected panels' tests for the user to review and correct
      patient   - the patient's age and sex from the report header (see extract_patient)
      analyses  - a per-panel analysis (model inputs, findings, indices, models) for
                  every panel with enough tests present (see analysis.py)
      unparsed  - lines that contain both letters and digits but didn't match a
                  result row (useful for spotting layouts the rules miss)
    report is None if the PDF has no extractable text (e.g. a scanned image).
    """
    with pymupdf.open(stream=contents, filetype="pdf") as pdf:
        pages = [_page_lines(page) for page in pdf.pages(0, min(max_pages, pdf.page_count))]
    if not any(pages):
        return None, len(pages)

    patient = extract_patient(pages)

    # Lines repeated on most pages are headers/footers (patient info, lab address).
    boilerplate = set()
    if len(pages) > 1:
        counts = Counter(line for lines in pages for line in set(lines))
        boilerplate = {line for line, n in counts.items() if n >= max(2, len(pages) / 2)}

    results, unparsed = [], []
    section = None
    for page_num, lines in enumerate(pages, start=1):
        for line in lines:
            if line in boilerplate or PAGE_NUMBER_RE.match(line):
                continue
            parsed = parse_result_line(line)
            if parsed:
                results += [{**r, "section": section, "page": page_num} for r in parsed]
            elif _is_section_header(line):
                section = line
            elif re.search(r"[A-Za-z]", line) and re.search(r"\d", line):
                unparsed.append({"line": line, "page": page_num})

    results = derive(enrich(results))
    panels = detect_panels(results)
    report = {
        "results": results,
        "panels": panels,
        "biomarkers": review_list(results, panels),
        "patient": patient,
        "analyses": available_analyses(results, patient),
        "unparsed": unparsed,
    }
    return report, len(pages)

