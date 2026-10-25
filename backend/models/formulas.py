"""Published clinical formulas, run as models (see the MODELS comment in analysis.py).

Each takes (inputs, context) and returns the common output shape. When an input
is missing the output has value None and lists what's `missing`, so the page can
say what the calculation needs; a formula that doesn't apply returns None.
Values in `context["values"]` are in each biomarker's canonical unit (biomarkers.py).
"""

import math


def _output(name, version, value=None, unit=None, interpretation=None, missing=()):
    return {
        "name": name,
        "value": None if value is None else round(value, 2),
        "unit": unit,
        "interpretation": interpretation if value is not None else "Needs " + ", ".join(missing) + ".",
        "model_version": version,
        "missing": list(missing),
    }


def _gather(context, tests, age=False, sex=False):
    """The canonical values of `tests` (plus age/sex), and the names of any missing."""
    values = {t: context["values"].get(t) for t in tests}
    missing = [t for t, v in values.items() if v is None]
    patient = context["patient"]
    if age:
        values["age"] = patient.get("age")
        if values["age"] is None:
            missing.append("age")
    if sex:
        values["sex"] = patient.get("sex")
        if values["sex"] is None:
            missing.append("sex")
    return values, missing


# --- Kidney ---

def egfr_ckd_epi_2021(inputs, context):
    """CKD-EPI 2021 creatinine equation, without race (Inker et al., NEJM 2021).

    eGFR = 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^-1.200 × 0.9938^age × 1.012 [if female],
    Scr in mg/dL, κ = 0.7 (F) / 0.9 (M), α = -0.241 (F) / -0.302 (M). Adults only.
    """
    name, version = "eGFR (CKD-EPI 2021)", "ckd-epi-2021"
    v, missing = _gather(context, ["Creatinine"], age=True, sex=True)
    if missing:
        return _output(name, version, missing=missing)
    if v["age"] < 18:
        return None  # the equation is for adults
    female = v["sex"] == "female"
    kappa, alpha = (0.7, -0.241) if female else (0.9, -0.302)
    ratio = v["Creatinine"] / kappa
    egfr = 142 * min(ratio, 1) ** alpha * max(ratio, 1) ** -1.200 * 0.9938 ** v["age"] * (1.012 if female else 1)
    category = next(label for cutoff, label in [
        (90, "G1 (normal or high)"), (60, "G2 (mildly decreased)"), (45, "G3a (mildly to moderately decreased)"),
        (30, "G3b (moderately to severely decreased)"), (15, "G4 (severely decreased)"), (0, "G5 (kidney failure range)"),
    ] if egfr >= cutoff)
    return _output(name, version, egfr, "mL/min/1.73m2",
                   f"GFR category {category}. Calculated from creatinine, age and sex; "
                   "CKD is diagnosed only with repeat tests or other signs of kidney damage.")


# --- Liver ---

def fib4(inputs, context):
    """FIB-4 = age × AST / (platelets × √ALT) (Sterling et al., Hepatology 2006).

    Below 1.30 (2.0 from age 65) advanced fibrosis is unlikely; above 2.67 it's likely;
    between is indeterminate. Less reliable under 35.
    """
    name, version = "FIB-4", "sterling-2006"
    v, missing = _gather(context, ["AST", "ALT", "Platelets"], age=True)
    if missing:
        return _output(name, version, missing=missing)
    if not v["ALT"] or not v["Platelets"]:
        return None
    score = v["age"] * v["AST"] / (v["Platelets"] * math.sqrt(v["ALT"]))
    low = 2.0 if v["age"] >= 65 else 1.30
    band = ("advanced liver scarring is unlikely" if score < low
            else "advanced liver scarring is likely; follow-up testing is usually advised" if score > 2.67
            else "indeterminate; often followed by other tests such as elastography")
    caveat = " FIB-4 is less reliable under age 35." if v["age"] < 35 else ""
    return _output(name, version, score, None, f"Liver fibrosis score: {band}.{caveat}")


def apri(inputs, context):
    """APRI = (AST / AST upper limit of normal) / platelets × 100 (Wai et al., Hepatology 2003).

    Uses the report's own AST upper limit, or 40 U/L when none is printed.
    Below 0.5 significant fibrosis is unlikely; above 1.5 it's likely.
    """
    name, version = "APRI", "wai-2003"
    v, missing = _gather(context, ["AST", "Platelets"])
    if missing:
        return _output(name, version, missing=missing)
    if not v["Platelets"]:
        return None
    # AST's units (U/L, IU/L) are all equivalent, so the printed limit can be used as is.
    printed_uln = (context["results"].get("AST") or {}).get("ref_high")
    uln = printed_uln or 40
    score = (v["AST"] / uln) / v["Platelets"] * 100
    band = ("significant liver scarring is unlikely" if score < 0.5
            else "significant liver scarring is likely" if score > 1.5 else "indeterminate")
    source = f"the report's AST upper limit ({uln:g} U/L)" if printed_uln else "an assumed AST upper limit of 40 U/L"
    return _output(name, version, score, None, f"AST-to-platelet ratio: {band}. Uses {source}.")


# --- Blood count ---

def mentzer_index(inputs, context):
    """Mentzer index = MCV / RBC (Mentzer, Lancet 1973), only for small red cells (MCV < 80 fL).

    Below 13 points toward thalassemia trait, above 13 toward iron deficiency.
    """
    name, version = "Mentzer index", "mentzer-1973"
    v, missing = _gather(context, ["MCV", "Red Blood Cells"])
    if missing or v["MCV"] >= 80 or not v["Red Blood Cells"]:
        return None  # only meaningful when red cells are small
    index = v["MCV"] / v["Red Blood Cells"]
    lean = "thalassemia trait" if index < 13 else "iron deficiency"
    return _output(name, version, index, None,
                   f"Red cells are small (MCV {v['MCV']:g} fL); this index points more toward {lean}. "
                   "It's a screening hint, confirmed with iron studies or hemoglobin electrophoresis.")


# --- Whole report ---

PHENOAGE_TESTS = ["Albumin", "Creatinine", "Glucose", "CRP", "Lymphocytes %", "MCV", "RDW", "Alkaline Phosphatase",
                  "White Blood Cells"]


def phenoage(inputs, context):
    """Phenotypic age (Levine et al., Aging 2018), constants as in the BioAge reference code.

    xb = -19.907 - 0.0336 albumin[g/L] + 0.0095 creatinine[umol/L] + 0.1953 glucose[mmol/L]
         + 0.0954 ln(CRP[mg/dL]) - 0.0120 lymphocyte% + 0.0268 MCV + 0.3306 RDW
         + 0.00188 ALP + 0.0554 WBC[10^3/uL] + 0.0804 age
    mortality = 1 - exp(-exp(xb) × (exp(120 γ) - 1) / γ), γ = 0.0076927
    PhenoAge = 141.50225 + ln(-0.0055305 × ln(1 - mortality)) / 0.090165
    """
    name, version = "Biological age (PhenoAge)", "levine-2018"
    values = dict(context["values"])
    if values.get("CRP") is None:
        values["CRP"] = values.get("hs-CRP")
    v, missing = _gather({**context, "values": values}, PHENOAGE_TESTS, age=True)
    if missing:
        return _output(name, version, missing=missing)
    if v["CRP"] <= 0:
        return None
    xb = (-19.907
          - 0.0336 * v["Albumin"] * 10              # g/dL -> g/L
          + 0.0095 * v["Creatinine"] * 88.4         # mg/dL -> umol/L
          + 0.1953 * v["Glucose"] / 18.016          # mg/dL -> mmol/L
          + 0.0954 * math.log(v["CRP"] / 10)        # mg/L -> mg/dL
          - 0.0120 * v["Lymphocytes %"]
          + 0.0268 * v["MCV"]
          + 0.3306 * v["RDW"]
          + 0.00188 * v["Alkaline Phosphatase"]
          + 0.0554 * v["White Blood Cells"]
          + 0.0804 * v["age"])
    gamma = 0.0076927
    mortality = 1 - math.exp(-math.exp(xb) * (math.exp(120 * gamma) - 1) / gamma)
    if not 0 < mortality < 1:
        return None
    age_estimate = 141.50225 + math.log(-0.0055305 * math.log(1 - mortality)) / 0.090165
    gap = age_estimate - v["age"]
    direction = f"{abs(gap):.1f} years {'older' if gap > 0 else 'younger'} than" if abs(gap) >= 0.5 else "about the same as"
    return _output(name, version, age_estimate, "years",
                   f"{direction} actual age ({v['age']:g}), estimated from 9 routine blood tests. "
                   "A research measure of aging, not a diagnosis; glucose should be fasting.")
