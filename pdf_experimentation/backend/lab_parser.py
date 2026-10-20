"""Fast, rule-based parsing of blood test report PDFs.

Text is pulled out with PyMuPDF and rebuilt into visual lines from span
coordinates, skipping text a reader can't see (hidden watermarks) and small
print under a test name (the test method). Each line is then matched against
the shape of a result row:

    <test name>  [flag]  <value>[flag]  [flag]  [unit]  [reference range]

where the unit and reference range may come in either order. A line only
counts as a result if its value is followed by a unit or a reference range,
which keeps page headers, addresses and phone numbers out of the results.
"""

import re
from collections import Counter

import pymupdf

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
UNIT_WORDS = {"%", "fl", "pg", "g", "sec", "seconds", "mmhg", "units", "iu", "u"}

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

# Canonical test name -> the spellings labs commonly use for it. Matching is
# exact (after normalization) on purpose: fuzzy matching confuses pairs like
# "HDL Cholesterol" and "LDL Cholesterol".
CANONICAL_TESTS = {
    # Complete blood count
    "White Blood Cells": ["wbc", "wbc count", "total wbc count", "total leukocyte count", "tlc", "white blood cell count", "white blood cells", "leukocytes", "white blood count"],
    "Red Blood Cells": ["rbc", "rbc count", "red blood cell count", "red blood cells", "erythrocytes", "red blood count"],
    "Hemoglobin": ["hemoglobin", "hgb", "hb"],
    "Hematocrit": ["hematocrit", "hct"],
    "MCV": ["mcv", "mean corpuscular volume"],
    "MCH": ["mch", "mean corpuscular hemoglobin"],
    "MCHC": ["mchc", "mean corpuscular hemoglobin concentration"],
    "RDW": ["rdw", "rdw cv", "red cell distribution width"],
    "Platelets": ["platelets", "platelet count", "plt"],
    "MPV": ["mpv", "mean platelet volume"],
    "Neutrophils %": ["neutrophils", "neutrophils %", "neut %", "neutrophils percent"],
    "Lymphocytes %": ["lymphs", "lymphocytes", "lymphocytes %", "lymph %"],
    "Monocytes %": ["monocytes", "monocytes %", "mono %"],
    "Eosinophils %": ["eos", "eosinophils", "eosinophils %", "eos %"],
    "Basophils %": ["basos", "basophils", "basophils %", "baso %"],
    "Neutrophils (Absolute)": ["neutrophils absolute", "absolute neutrophils", "neutrophils abs", "anc"],
    "Lymphocytes (Absolute)": ["lymphocytes absolute", "absolute lymphocytes", "lymphs absolute", "lymphs abs"],
    "Monocytes (Absolute)": ["monocytes absolute", "absolute monocytes", "monocytes abs"],
    "Eosinophils (Absolute)": ["eosinophils absolute", "absolute eosinophils", "eos absolute", "eos abs"],
    "Basophils (Absolute)": ["basophils absolute", "absolute basophils", "baso absolute", "basos absolute"],
    # Metabolic panel
    "Glucose": ["glucose", "glucose fasting", "fasting glucose", "glu", "fasting blood sugar", "fbs"],
    "Urea": ["urea", "blood urea"],
    "Uric Acid": ["uric acid"],
    "BUN": ["bun", "urea nitrogen", "blood urea nitrogen", "urea nitrogen bun"],
    "Creatinine": ["creatinine", "creat"],
    "eGFR": ["egfr", "gfr", "estimated gfr", "egfr non afr american", "egfr if nonafricn am"],
    "BUN/Creatinine Ratio": ["bun creatinine ratio", "bun creat ratio"],
    "Sodium": ["sodium", "na"],
    "Potassium": ["potassium", "k"],
    "Chloride": ["chloride", "cl"],
    "Carbon Dioxide": ["carbon dioxide", "co2", "bicarbonate", "carbon dioxide total"],
    "Calcium": ["calcium", "ca"],
    "Total Protein": ["protein total", "total protein", "protein"],
    "Albumin": ["albumin"],
    "Globulin": ["globulin", "globulin total"],
    "Albumin/Globulin Ratio": ["a g ratio", "albumin globulin ratio"],
    "Bilirubin, Total": ["bilirubin total", "total bilirubin", "bilirubin"],
    "Alkaline Phosphatase": ["alkaline phosphatase", "alk phos", "alp"],
    "AST": ["ast", "ast sgot", "sgot", "aspartate aminotransferase"],
    "ALT": ["alt", "alt sgpt", "sgpt", "alanine aminotransferase"],
    # Lipids
    "Total Cholesterol": ["cholesterol", "cholesterol total", "total cholesterol"],
    "HDL Cholesterol": ["hdl", "hdl cholesterol", "hdl c"],
    "LDL Cholesterol": ["ldl", "ldl cholesterol", "ldl c", "ldl chol calc", "ldl chol calc nih", "ldl cholesterol calc", "direct ldl", "ldl direct"],
    "Triglycerides": ["triglycerides", "triglyceride", "trig"],
    "VLDL Cholesterol": ["vldl", "vldl cholesterol"],
    "Non-HDL Cholesterol": ["non hdl cholesterol", "non hdl c"],
    "Cholesterol/HDL Ratio": ["chol hdl ratio", "cholesterol hdl ratio", "t chol hdl ratio"],
    # Diabetes, thyroid, vitamins, iron
    "Hemoglobin A1c": ["hemoglobin a1c", "hba1c", "a1c", "glycohemoglobin"],
    "TSH": ["tsh", "thyroid stimulating hormone", "tsh thyroid stimulating hormone"],
    "Free T4": ["free t4", "t4 free", "t4 free direct", "thyroxine free"],
    "Free T3": ["free t3", "t3 free"],
    "Total T3": ["t3", "t3 total", "total t3", "t3 triiodothyronine", "triiodothyronine"],
    "Total T4": ["t4", "t4 total", "total t4", "t4 thyroxine", "thyroxine"],
    "Vitamin D, 25-Hydroxy": ["vitamin d", "vitamin d 25 hydroxy", "25 hydroxy vitamin d", "vitamin d 25 oh", "25 oh vitamin d"],
    "Vitamin B12": ["vitamin b12", "b12", "cobalamin"],
    "Folate": ["folate", "folic acid"],
    "Iron": ["iron", "iron total"],
    "Ferritin": ["ferritin"],
    "Transferrin Saturation": ["transferrin saturation", "iron saturation"],
    "ESR": ["esr", "erythrocyte sedimentation rate", "sed rate"],
    "Homocysteine": ["homocysteine"],
    "PSA": ["psa", "psa total", "prostate specific antigen", "psa prostate specific antigen total"],
    "TIBC": ["tibc", "iron binding capacity", "total iron binding capacity"],
}


# The biomarkers pulled out of a report for the user to review and correct.
KEY_BIOMARKERS = ["Glucose", "Hemoglobin A1c", "Total Cholesterol", "LDL Cholesterol", "Hemoglobin"]


def _normalize_name(name):
    return " ".join(re.sub(r"[^a-z0-9%]+", " ", name.lower()).split())


def _strip_qualifiers(key):
    key = re.sub(r"\b(serum|plasma|blood|whole|calc)\b", " ", key)
    return " ".join(key.split())


ALIASES = {
    _normalize_name(alias): canonical
    for canonical, aliases in CANONICAL_TESTS.items()
    for alias in aliases + [canonical]
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


def parse_result_line(line):
    """Parse one text line into a list of result dicts (empty if it isn't a result row).

    A line holds two results when a differential count prints the percentage and
    the absolute count side by side: "Neutrophils 73 % 40-80 7716 /cmm 2000-6700".
    """
    line = SPLIT_UNIT_RE.sub(r"\1", UP_TO_RE.sub("<=", line))
    line = SPACED_BOUND_RE.sub(r"\1", SPACED_RANGE_RE.sub(r"\1-\2", line))
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


def extract_key_biomarkers(results):
    """One entry per KEY_BIOMARKERS name, in order: the first matching result
    (reports often repeat a test across panels), or an empty placeholder with
    found=False so the user can still fill it in."""
    biomarkers = []
    for name in KEY_BIOMARKERS:
        match = next((r for r in results if r["canonical"] == name), None)
        if match is not None:
            biomarkers.append({**match, "found": True})
        else:
            biomarkers.append({
                "test": name, "canonical": name, "value": None, "value_text": None,
                "unit": None, "flag": None, "reference_range": None,
                "ref_low": None, "ref_high": None, "found": False,
            })
    return biomarkers


def parse_lab_report(contents, max_pages):
    """Parse a PDF's bytes into lab results.

    Returns (report, num_pages), where report holds the parsed `results`,
    the `biomarkers` from KEY_BIOMARKERS, and `unparsed` lines that contain both letters and digits but didn't
    match a result row (useful for spotting layouts the rules miss).
    report is None if the PDF has no extractable text (e.g. a scanned image).
    """
    with pymupdf.open(stream=contents, filetype="pdf") as pdf:
        pages = [_page_lines(page) for page in pdf.pages(0, min(max_pages, pdf.page_count))]
    if not any(pages):
        return None, len(pages)

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

    report = {"results": results, "biomarkers": extract_key_biomarkers(results), "unparsed": unparsed}
    return report, len(pages)

