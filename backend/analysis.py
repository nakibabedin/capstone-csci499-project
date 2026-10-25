"""Per-panel analysis: the unit that future ML models plug into.

A report rarely has every panel, so each panel is analyzed on its own whenever
enough of its tests are present, whichever panel the lab ordered them under
(a CMP report also gets Liver and Kidney analyses). An analysis holds:

    inputs   -> the panel's model inputs in a fixed order and canonical units
                (PANELS[...]["inputs"], versioned by "schema_version"), None where
                missing, plus whether each was out of range on the report
    findings -> the panel's results that are out of range, abnormal or implausible
    indices  -> standard ratios computed from the report's values (NLR, HOMA-IR, ...)
    model    -> the output of the panel's model in MODELS, or None until one exists

Which panels the lab ordered (for display) is panels.detect_panels; this module
doesn't depend on it.
"""

import logging
import math

from biomarkers import PANELS
from status import result_status

log = logging.getLogger(__name__)

# panel id -> callable(inputs) -> dict, e.g. {"prediction": 0.12, "model_version": "2026-11"}.
# A model receives the panel's `inputs` (see _inputs) and must accept None for missing values.
# Registering a trained model here is all it takes to add it to that panel's analysis.
MODELS = {}


def _alternatives(member):
    return member if isinstance(member, tuple) else (member,)


# Tests that belong to only one panel. A panel with one or two required tests needs
# one of these, so that a CMP's glucose alone doesn't produce a Diabetes analysis.
OWN_TESTS = {
    panel_id: set(panel["inputs"]).difference(*(other["inputs"] for other_id, other in PANELS.items() if other_id != panel_id))
    for panel_id, panel in PANELS.items()
}


def _first_results(results):
    """Canonical name -> its first result with a value or answer, preferring usable
    (not suspect) and reported (not derived) ones."""
    first = {}
    for r in sorted(results, key=lambda r: (bool(r.get("suspect")), bool(r.get("derived")))):
        if r.get("canonical") and (r.get("value") is not None or r.get("value_text")):
            first.setdefault(r["canonical"], r)
    return first


def _encode(result):
    """A result as one model input: its canonical-unit value, or 0/1 for a normal/abnormal
    word answer. None if missing, implausible, or a word answer that isn't a health signal.

    A test reported either way (an infection screen prints "0.07 S/Co" or just "Non
    Reactive") encodes as its index in one report and 0/1 in another, so models should
    pair it with `out_of_range`, which means the same thing in both."""
    if result is None or result.get("suspect"):
        return None
    if result.get("value_std") is not None:
        return result["value_std"]
    return {"normal": 0, "abnormal": 1}.get(result.get("text_status"))


def _is_missing(result):
    """Not on the report, implausible, or a number in a unit we can't convert.
    An informational answer (a blood group) is present even though it encodes to None."""
    if result is None or result.get("suspect"):
        return True
    return result.get("value") is not None and result.get("value_std") is None


def _out_of_range(result):
    """1 if the report marks the result out of range or abnormal, 0 if normal, None if unknown."""
    if result is None:
        return None
    status = result_status(result)
    return None if status == "unknown" else int(status != "normal")


def _is_available(panel_id, found):
    panel = PANELS[panel_id]
    required = panel["required"]
    if required:
        hits = sum(1 for m in required if found & set(_alternatives(m)))
        if hits == 0 or hits < panel["min_coverage"] * len(required):
            return False
    elif not found & set(panel["inputs"]):
        return False
    return len(required) > 2 or bool(found & OWN_TESTS[panel_id])


def _inputs(panel, first):
    names = panel["inputs"]
    return {
        "schema_version": panel["schema_version"],
        "values": {name: _encode(first.get(name)) for name in names},
        "out_of_range": {name: _out_of_range(first.get(name)) for name in names},
        "missing": [name for name in names if _is_missing(first.get(name))],
    }


def _findings(panel, results):
    findings = []
    for r in results:
        if r.get("canonical") not in panel["inputs"] or r.get("derived"):
            continue
        status = result_status(r)
        if r.get("suspect") or status not in ("normal", "unknown"):
            findings.append({
                "test": r["canonical"],
                "value_text": r.get("value_text"),
                "unit": r.get("unit"),
                "reference_range": r.get("reference_range"),
                "status": status.lower(),
                "suspect": bool(r.get("suspect")),
            })
    return findings


# --- Indices: (name, formula over canonical values, note), skipped when an input is missing ---

def _ratio(a, b):
    return a / b if a is not None and b else None


def _first_of(*values):
    return next((v for v in values if v is not None), None)


def _aip(v):
    """Atherogenic index of plasma: log10 of TG/HDL with both in mmol/L."""
    ratio = _ratio(v.get("Triglycerides") and v["Triglycerides"] / 88.57, v.get("HDL Cholesterol") and v["HDL Cholesterol"] / 38.67)
    return math.log10(ratio) if ratio else None


INDICES = {
    "differential": [
        ("Neutrophil-to-lymphocyte ratio",
         lambda v: _first_of(_ratio(v.get("Neutrophils (Absolute)"), v.get("Lymphocytes (Absolute)")),
                             _ratio(v.get("Neutrophils %"), v.get("Lymphocytes %"))),
         "Neutrophils divided by lymphocytes; a general marker of inflammation and physiological stress."),
        ("Platelet-to-lymphocyte ratio",
         lambda v: _ratio(v.get("Platelets"), v.get("Lymphocytes (Absolute)")),
         "Platelets divided by lymphocytes (both in thousands per microlitre)."),
    ],
    "lipid": [
        ("Triglyceride-to-HDL ratio", lambda v: _ratio(v.get("Triglycerides"), v.get("HDL Cholesterol")),
         "Triglycerides divided by HDL, both in mg/dL; often used as a marker of insulin resistance."),
        ("Atherogenic index of plasma", _aip, "log10(triglycerides / HDL) with both in mmol/L."),
    ],
    "liver": [
        ("De Ritis ratio (AST/ALT)", lambda v: _ratio(v.get("AST"), v.get("ALT")),
         "AST divided by ALT; describes the pattern of a liver enzyme rise."),
    ],
    "diabetes": [
        ("HOMA-IR", lambda v: v["Glucose"] * v["Insulin"] / 405 if v.get("Glucose") is not None and v.get("Insulin") is not None else None,
         "Glucose (mg/dL) × insulin (uIU/mL) / 405; estimates insulin resistance. Assumes both were fasting."),
    ],
    "iron": [
        ("Transferrin saturation (calculated)",
         lambda v: None if v.get("Transferrin Saturation") is not None else _ratio(v.get("Iron"), v.get("TIBC")) and 100 * v["Iron"] / v["TIBC"],
         "Iron divided by TIBC, as a percentage; shown only when the report doesn't print it."),
    ],
    "reproductive": [
        ("Free androgen index",
         lambda v: _ratio(v.get("Testosterone") and v["Testosterone"] / 28.84 * 100, v.get("SHBG")),
         "Total testosterone (nmol/L) × 100 / SHBG (nmol/L)."),
        ("LH/FSH ratio", lambda v: _ratio(v.get("LH"), v.get("FSH")), "LH divided by FSH."),
    ],
    "cardiovascular_risk": [
        ("ApoB/ApoA1 ratio", lambda v: _ratio(v.get("Apolipoprotein B"), v.get("Apolipoprotein A1")),
         "Apolipoprotein B divided by apolipoprotein A1."),
    ],
    "tumor_markers": [
        ("Free PSA percentage", lambda v: _ratio(v.get("Free PSA"), v.get("PSA")) and 100 * v["Free PSA"] / v["PSA"],
         "Free PSA as a percentage of total PSA."),
    ],
}


def _indices(panel_id, values):
    indices = []
    for name, formula, note in INDICES.get(panel_id, []):
        value = formula(values)
        if value is not None:
            indices.append({"name": name, "value": round(value, 3 if abs(value) < 1 else 2), "note": note})
    return indices


def _model(panel_id, inputs):
    model = MODELS.get(panel_id)
    if model is None:
        return None
    try:
        return model(inputs)
    except Exception as e:  # a broken model must not break the report
        log.exception("Model for panel %s failed", panel_id)
        return {"error": str(e)}


def available_analyses(results):
    """An analysis for every panel with enough of its tests present, in PANELS order.

    `results` are enriched (and usually derived) results; see panels.enrich and derive.
    """
    first = _first_results(results)
    found = {name for name, r in first.items() if not r.get("derived")}
    values = {name: r["value_std"] for name, r in first.items() if r.get("value_std") is not None and not r.get("suspect")}
    analyses = []
    for panel_id, panel in PANELS.items():
        if not _is_available(panel_id, found):
            continue
        inputs = _inputs(panel, first)
        analyses.append({
            "id": panel_id,
            "name": panel["name"],
            "coverage": round(1 - len(inputs["missing"]) / len(panel["inputs"]), 2),
            "inputs": inputs,
            "findings": _findings(panel, results),
            "indices": _indices(panel_id, values),
            "model": _model(panel_id, inputs),
        })
    return analyses
