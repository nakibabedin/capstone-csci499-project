"""Panel detection and ML-ready enrichment of parsed lab results.

    enrich         -> each result gets a LOINC code, a value in its canonical unit,
                      and a `suspect` flag when that value is physiologically implausible
    derive         -> values a report left out but that follow from others (Non-HDL, Globulin, ...)
    detect_panels  -> which test panels the report contains, and their missing tests
    review_list    -> the tests of the detected panels, for the user to check and correct

Per-panel model inputs and analysis live in analysis.py.
"""

from biomarkers import BIOMARKERS, PANELS, normalize_answer
from units import normalize_unit, to_canonical

# A differential count's percentage and absolute count often share a printed name
# ("Neutrophils"); the unit tells them apart.
PERCENT_TO_ABSOLUTE = {
    "Neutrophils %": "Neutrophils (Absolute)",
    "Lymphocytes %": "Lymphocytes (Absolute)",
    "Monocytes %": "Monocytes (Absolute)",
    "Eosinophils %": "Eosinophils (Absolute)",
    "Basophils %": "Basophils (Absolute)",
}

# A panel counts as present when at least this fraction of its required tests was found.
DETECTION_THRESHOLD = 0.5


def enrich(results):
    """Copies of the results with `canonical` corrected for differential counts,
    plus `kind`, `loinc`, `value_std`, `unit_std` and `suspect`, and for a word
    answer its `text_status` ("normal", "abnormal", or None if it isn't a health
    signal or isn't a known answer)."""
    enriched = []
    for r in results:
        canonical = r.get("canonical")
        if canonical in PERCENT_TO_ABSOLUTE and normalize_unit(r.get("unit")) not in (None, "%"):
            canonical = PERCENT_TO_ABSOLUTE[canonical]
        biomarker = BIOMARKERS.get(canonical)
        value_std, unit_std = to_canonical(canonical, r.get("value"), r.get("unit"))
        low, high = (biomarker or {}).get("plausible") or (None, None)
        text_status = None
        if biomarker and r.get("value") is None and r.get("value_text"):
            text_status = biomarker["answers"].get(normalize_answer(r["value_text"]))
        enriched.append({
            **r,
            "canonical": canonical,
            "kind": biomarker["kind"] if biomarker else None,
            "loinc": biomarker["loinc"] if biomarker else None,
            "value_std": value_std,
            "unit_std": unit_std,
            "suspect": value_std is not None and low is not None and not low <= value_std <= high,
            "text_status": text_status,
        })
    return enriched


def _first_values(results):
    """Canonical name -> value_std of its first usable result."""
    values = {}
    for r in results:
        if r.get("canonical") and r.get("value_std") is not None and not r.get("suspect"):
            values.setdefault(r["canonical"], r["value_std"])
    return values


# Derived biomarker -> (inputs, formula over the inputs' canonical values), in
# dependency order: BUN before BUN/Creatinine Ratio, Globulin before the A/G ratio.
DERIVATIONS = {
    "BUN": (["Urea"], lambda urea: urea * 0.467),
    "Non-HDL Cholesterol": (["Total Cholesterol", "HDL Cholesterol"], lambda tc, hdl: tc - hdl),
    "Globulin": (["Total Protein", "Albumin"], lambda tp, alb: tp - alb),
    "Albumin/Globulin Ratio": (["Albumin", "Globulin"], lambda alb, glob: alb / glob if glob else None),
    "BUN/Creatinine Ratio": (["BUN", "Creatinine"], lambda bun, cr: bun / cr if cr else None),
    "Anion Gap": (["Sodium", "Chloride", "Carbon Dioxide"], lambda na, cl, co2: na - cl - co2),
    "Bilirubin, Indirect": (["Bilirubin, Total", "Bilirubin, Direct"], lambda total, direct: total - direct),
}


def derive(results):
    """The results plus derived ones (marked `derived: True`) for biomarkers the
    report left out but that can be calculated from ones it has."""
    values = _first_values(results)
    derived = []
    for name, (inputs, formula) in DERIVATIONS.items():
        if name in values or not all(i in values for i in inputs):
            continue
        value = formula(*(values[i] for i in inputs))
        if value is None:
            continue
        value = round(value, 2)
        values[name] = value
        low, high = BIOMARKERS[name]["plausible"]
        unit = BIOMARKERS[name]["unit"]
        derived.append({
            "test": name, "canonical": name, "value": value, "value_text": str(value),
            "unit": unit, "flag": None, "reference_range": None, "ref_low": None, "ref_high": None,
            "section": None, "page": None, "loinc": BIOMARKERS[name]["loinc"],
            "value_std": value, "unit_std": unit, "suspect": not low <= value <= high, "derived": True,
        })
    return results + derived


def _alternatives(member):
    return member if isinstance(member, tuple) else (member,)


def _members(panel):
    return {name for m in panel["required"] + panel["optional"] for name in _alternatives(m)}


def detect_panels(results):
    """The panels a report contains, in PANELS order.

    A panel is detected when at least half its required tests were found, or a
    section heading names it. To keep a CMP from also showing up as a BMP, or a
    lipid panel's tests from triggering other panels, a panel must also have at
    least one found test that isn't part of a panel already detected, and a panel
    that `extends` a smaller one needs a found test beyond the smaller panel's.
    """
    found = {r["canonical"] for r in results if r.get("canonical") and not r.get("derived")}
    sections = {(r.get("section") or "").lower() for r in results}
    covered = set()
    detected = []
    for panel_id, panel in PANELS.items():
        members = _members(panel)
        present = members & found
        required_found = [m for m in panel["required"] if found & set(_alternatives(m))]
        named = any(k in s for k in panel["section_keywords"] for s in sections)
        enough = len(required_found) >= DETECTION_THRESHOLD * len(panel["required"])
        beyond_base = present - _members(PANELS[panel["extends"]]) if "extends" in panel else present
        if not beyond_base or not (enough or named) or not (present - covered or named):
            continue
        covered |= members
        missing = [_alternatives(m)[0] for m in panel["required"] if m not in required_found]
        detected.append({
            "id": panel_id,
            "name": panel["name"],
            "status": "complete" if not missing else "partial",
            "found": sorted(present, key=list(BIOMARKERS).index),
            "missing": missing,
        })
    return detected


def review_list(results, panels):
    """The detected panels' required tests (plus any optional ones found), each under
    its first panel: the first parsed result for it, or a found=False placeholder.

    Each carries its `canonical_unit` and `plausible` range so the editor can flag
    an implausible value after the user changes it, and its known `answers` so
    the editor can offer them for word-answer tests."""
    parsed = [r for r in results if not r.get("derived")]
    seen, biomarkers = set(), []
    for panel in panels:
        spec = PANELS[panel["id"]]
        names = [next((n for n in _alternatives(m) if n in panel["found"]), _alternatives(m)[0]) for m in spec["required"]]
        names += [n for n in spec["optional"] if n in panel["found"]]
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            match = next((r for r in parsed if r.get("canonical") == name), None)
            plausible = BIOMARKERS[name]["plausible"]
            spec_fields = {
                "panel": panel["id"],
                "kind": BIOMARKERS[name]["kind"],
                "canonical_unit": BIOMARKERS[name]["unit"],
                "plausible": list(plausible) if plausible else None,
                "answers": BIOMARKERS[name]["answers"],
            }
            if match is not None:
                biomarkers.append({**match, **spec_fields, "found": True})
            else:
                biomarkers.append({
                    "test": name, "canonical": name, "value": None, "value_text": None,
                    "unit": BIOMARKERS[name]["unit"], "flag": None, "reference_range": None,
                    "ref_low": None, "ref_high": None, "loinc": BIOMARKERS[name]["loinc"],
                    "value_std": None, "unit_std": None, "suspect": False,
                    **spec_fields, "found": False,
                })
    return biomarkers
