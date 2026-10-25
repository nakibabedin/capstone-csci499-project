"""Registry of the biomarkers and test panels the app knows about.

Each biomarker has the spellings labs use for it, a LOINC code (the standard
identifier for lab tests, used to line up our data with other datasets), the
NHANES variable that measures it (None where there isn't one or it's unverified),
the canonical unit values are converted to, conversions from other units, and a
plausible range used to catch misread values. Check the NHANES names against the
NHANES codebooks before using them to build training data.

Conversions map a normalized unit (see units.normalize_unit) to either a factor
or a (factor, offset) pair: canonical = value * factor + offset.
"""

COUNT_THOUSANDS = {"10^3/uL": 1, "10^9/L": 1, "/uL": 0.001, "10^5/uL": 100}
PERCENT = {"%": 1}
CHOLESTEROL = {"mg/dL": 1, "mmol/L": 38.67}
PROTEIN = {"g/dL": 1, "g/L": 0.1}
BILIRUBIN = {"mg/dL": 1, "umol/L": 1 / 17.1}
ENZYME = {"U/L": 1, "IU/L": 1}
ELECTROLYTE = {"mmol/L": 1, "mEq/L": 1}
RATIO = {None: 1}


def _b(aliases, loinc, unit, plausible, conversions, nhanes=None):
    return {
        "aliases": aliases,
        "loinc": loinc,
        "nhanes": nhanes,
        "unit": unit,
        "conversions": conversions,
        "plausible": plausible,
    }


# Canonical name -> biomarker. Alias matching is exact (after normalization) on
# purpose: fuzzy matching confuses pairs like "HDL Cholesterol" and "LDL Cholesterol".
BIOMARKERS = {
    # Complete blood count
    "White Blood Cells": _b(["wbc", "wbc count", "total wbc count", "total leukocyte count", "tlc", "white blood cell count", "white blood cells", "leukocytes", "white blood count"],
                            "6690-2", "10^3/uL", (0.1, 200), COUNT_THOUSANDS, "LBXWBCSI"),
    "Red Blood Cells": _b(["rbc", "rbc count", "red blood cell count", "red blood cells", "erythrocytes", "red blood count"],
                          "789-8", "10^6/uL", (0.5, 10), {"10^6/uL": 1, "10^12/L": 1}, "LBXRBCSI"),
    "Hemoglobin": _b(["hemoglobin", "hgb", "hb"], "718-7", "g/dL", (2, 25), {"g/dL": 1, "g/L": 0.1, "mmol/L": 1.611}, "LBXHGB"),
    "Hematocrit": _b(["hematocrit", "hct", "pcv", "packed cell volume"], "4544-3", "%", (5, 75), {"%": 1, "L/L": 100}, "LBXHCT"),
    "MCV": _b(["mcv", "mean corpuscular volume"], "787-2", "fL", (40, 150), {"fL": 1}, "LBXMCVSI"),
    "MCH": _b(["mch", "mean corpuscular hemoglobin"], "785-6", "pg", (10, 50), {"pg": 1}, "LBXMCHSI"),
    "MCHC": _b(["mchc", "mean corpuscular hemoglobin concentration"], "786-4", "g/dL", (20, 45), PROTEIN, "LBXMC"),
    "RDW": _b(["rdw", "rdw cv", "red cell distribution width"], "788-0", "%", (8, 40), PERCENT, "LBXRDW"),
    "Platelets": _b(["platelets", "platelet count", "plt"], "777-3", "10^3/uL", (1, 2000), COUNT_THOUSANDS, "LBXPLTSI"),
    "MPV": _b(["mpv", "mean platelet volume"], "32623-1", "fL", (5, 20), {"fL": 1}, "LBXMPSI"),
    "Neutrophils %": _b(["neutrophils", "neutrophils %", "neut %", "neutrophils percent"], "770-8", "%", (0, 100), PERCENT, "LBXNEPCT"),
    "Lymphocytes %": _b(["lymphs", "lymphocytes", "lymphocytes %", "lymph %"], "736-9", "%", (0, 100), PERCENT, "LBXLYPCT"),
    "Monocytes %": _b(["monocytes", "monocytes %", "mono %"], "5905-5", "%", (0, 100), PERCENT, "LBXMOPCT"),
    "Eosinophils %": _b(["eos", "eosinophils", "eosinophils %", "eos %"], "713-8", "%", (0, 100), PERCENT, "LBXEOPCT"),
    "Basophils %": _b(["basos", "basophils", "basophils %", "baso %"], "706-2", "%", (0, 100), PERCENT, "LBXBAPCT"),
    "Neutrophils (Absolute)": _b(["neutrophils absolute", "absolute neutrophils", "neutrophils abs", "anc", "neutrophils absolute count"],
                                 "751-8", "10^3/uL", (0, 100), COUNT_THOUSANDS, "LBDNENO"),
    "Lymphocytes (Absolute)": _b(["lymphocytes absolute", "absolute lymphocytes", "lymphs absolute", "lymphs abs", "lymphocytes absolute count"],
                                 "731-0", "10^3/uL", (0, 100), COUNT_THOUSANDS, "LBDLYMNO"),
    "Monocytes (Absolute)": _b(["monocytes absolute", "absolute monocytes", "monocytes abs", "monocytes absolute count"],
                               "742-7", "10^3/uL", (0, 50), COUNT_THOUSANDS, "LBDMONO"),
    "Eosinophils (Absolute)": _b(["eosinophils absolute", "absolute eosinophils", "eos absolute", "eos abs", "eosinophils absolute count"],
                                 "711-2", "10^3/uL", (0, 50), COUNT_THOUSANDS, "LBDEONO"),
    "Basophils (Absolute)": _b(["basophils absolute", "absolute basophils", "baso absolute", "basos absolute", "basophils absolute count"],
                               "704-7", "10^3/uL", (0, 20), COUNT_THOUSANDS, "LBDBANO"),
    # Metabolic panel
    "Glucose": _b(["glucose", "glucose fasting", "fasting glucose", "glu", "fasting blood sugar", "fbs"],
                  "2345-7", "mg/dL", (10, 1500), {"mg/dL": 1, "mmol/L": 18.016}, "LBXGLU"),
    "Urea": _b(["urea", "blood urea"], "3091-6", "mg/dL", (2, 430), {"mg/dL": 1, "mmol/L": 6.006}),
    "BUN": _b(["bun", "urea nitrogen", "blood urea nitrogen", "urea nitrogen bun"], "3094-0", "mg/dL", (1, 200), {"mg/dL": 1, "mmol/L": 2.801}, "LBXSBU"),
    "Creatinine": _b(["creatinine", "creat"], "2160-0", "mg/dL", (0.1, 25), {"mg/dL": 1, "umol/L": 1 / 88.4}, "LBXSCR"),
    "eGFR": _b(["egfr", "gfr", "estimated gfr", "egfr non afr american", "egfr if nonafricn am"],
               "33914-3", "mL/min/1.73m2", (1, 200), {"mL/min/1.73m2": 1}),
    "BUN/Creatinine Ratio": _b(["bun creatinine ratio", "bun creat ratio"], "3097-3", None, (1, 100), RATIO),
    "Sodium": _b(["sodium", "na"], "2951-2", "mmol/L", (100, 180), ELECTROLYTE, "LBXSNASI"),
    "Potassium": _b(["potassium", "k"], "2823-3", "mmol/L", (1.5, 10), ELECTROLYTE, "LBXSKSI"),
    "Chloride": _b(["chloride", "cl"], "2075-0", "mmol/L", (60, 140), ELECTROLYTE, "LBXSCLSI"),
    "Carbon Dioxide": _b(["carbon dioxide", "co2", "bicarbonate", "carbon dioxide total"], "2028-9", "mmol/L", (5, 50), ELECTROLYTE, "LBXSC3SI"),
    "Anion Gap": _b(["anion gap"], "33037-3", "mmol/L", (0, 40), ELECTROLYTE),
    "Calcium": _b(["calcium", "ca"], "17861-6", "mg/dL", (4, 18), {"mg/dL": 1, "mmol/L": 4.008}, "LBXSCA"),
    "Magnesium": _b(["magnesium", "mg"], "19123-9", "mg/dL", (0.5, 8), {"mg/dL": 1, "mmol/L": 2.431, "mEq/L": 1.215}),
    "Phosphorus": _b(["phosphorus", "phosphate", "inorganic phosphorus"], "2777-1", "mg/dL", (0.5, 15), {"mg/dL": 1, "mmol/L": 3.097}, "LBXSPH"),
    "Uric Acid": _b(["uric acid"], "3084-1", "mg/dL", (0.5, 20), {"mg/dL": 1, "umol/L": 1 / 59.48}, "LBXSUA"),
    # Liver
    "Total Protein": _b(["protein total", "total protein", "protein"], "2885-2", "g/dL", (2, 15), PROTEIN, "LBXSTP"),
    "Albumin": _b(["albumin"], "1751-7", "g/dL", (0.5, 7), PROTEIN, "LBXSAL"),
    "Globulin": _b(["globulin", "globulin total"], "10834-0", "g/dL", (0.5, 10), PROTEIN, "LBXSGB"),
    "Albumin/Globulin Ratio": _b(["a g ratio", "albumin globulin ratio"], "1759-0", None, (0.1, 5), RATIO),
    "Bilirubin, Total": _b(["bilirubin total", "total bilirubin", "bilirubin"], "1975-2", "mg/dL", (0, 50), BILIRUBIN, "LBXSTB"),
    "Bilirubin, Direct": _b(["bilirubin direct", "direct bilirubin", "conjugated bilirubin", "bilirubin conjugated"], "1968-7", "mg/dL", (0, 30), BILIRUBIN),
    "Bilirubin, Indirect": _b(["bilirubin indirect", "indirect bilirubin", "unconjugated bilirubin", "bilirubin unconjugated"], "1971-1", "mg/dL", (0, 30), BILIRUBIN),
    "Alkaline Phosphatase": _b(["alkaline phosphatase", "alk phos", "alp"], "6768-6", "U/L", (5, 3000), ENZYME, "LBXSAPSI"),
    "AST": _b(["ast", "ast sgot", "sgot", "aspartate aminotransferase"], "1920-8", "U/L", (1, 10000), ENZYME, "LBXSASSI"),
    "ALT": _b(["alt", "alt sgpt", "sgpt", "alanine aminotransferase"], "1742-6", "U/L", (1, 10000), ENZYME, "LBXSATSI"),
    "GGT": _b(["ggt", "gamma gt", "ggtp", "gamma glutamyl transferase", "gamma glutamyltransferase"], "2324-2", "U/L", (1, 3000), ENZYME, "LBXSGTSI"),
    # Lipids
    "Total Cholesterol": _b(["cholesterol", "cholesterol total", "total cholesterol"], "2093-3", "mg/dL", (50, 1000), CHOLESTEROL, "LBXTC"),
    "HDL Cholesterol": _b(["hdl", "hdl cholesterol", "hdl c"], "2085-9", "mg/dL", (5, 200), CHOLESTEROL, "LBDHDD"),
    "LDL Cholesterol": _b(["ldl", "ldl cholesterol", "ldl c", "ldl chol calc", "ldl chol calc nih", "ldl cholesterol calc", "direct ldl", "ldl direct"],
                          "13457-7", "mg/dL", (5, 600), CHOLESTEROL, "LBDLDL"),
    "Triglycerides": _b(["triglycerides", "triglyceride", "trig"], "2571-8", "mg/dL", (10, 10000), {"mg/dL": 1, "mmol/L": 88.57}, "LBXTR"),
    "VLDL Cholesterol": _b(["vldl", "vldl cholesterol"], "13458-5", "mg/dL", (1, 300), CHOLESTEROL),
    "Non-HDL Cholesterol": _b(["non hdl cholesterol", "non hdl c"], "43396-1", "mg/dL", (10, 800), CHOLESTEROL),
    "Cholesterol/HDL Ratio": _b(["chol hdl ratio", "cholesterol hdl ratio", "t chol hdl ratio"], "9830-1", None, (0.5, 20), RATIO),
    "LDL/HDL Ratio": _b(["ldl hdl ratio"], "11054-4", None, (0.1, 20), RATIO),
    # Diabetes
    "Hemoglobin A1c": _b(["hemoglobin a1c", "hba1c", "a1c", "glycohemoglobin"], "4548-4", "%", (3, 20), {"%": 1, "mmol/mol": (0.09148, 2.152)}, "LBXGH"),
    "Estimated Average Glucose": _b(["estimated average glucose", "eag", "mean blood glucose"], "27353-2", "mg/dL", (50, 500), {"mg/dL": 1, "mmol/L": 18.016}),
    "Insulin": _b(["insulin", "insulin fasting", "fasting insulin"], "20448-7", "uIU/mL", (0.5, 500), {"uIU/mL": 1, "pmol/L": 1 / 6}, "LBXIN"),
    # Thyroid
    "TSH": _b(["tsh", "thyroid stimulating hormone", "tsh thyroid stimulating hormone"], "3016-3", "uIU/mL", (0.001, 200), {"uIU/mL": 1}, "LBXTSH1"),
    "Free T4": _b(["free t4", "t4 free", "t4 free direct", "thyroxine free", "ft4"], "3024-7", "ng/dL", (0.1, 10), {"ng/dL": 1, "pmol/L": 1 / 12.87}, "LBXT4F"),
    "Free T3": _b(["free t3", "t3 free", "ft3"], "3051-0", "pg/mL", (0.5, 30), {"pg/mL": 1, "pmol/L": 0.651}, "LBXT3F"),
    "Total T3": _b(["t3", "t3 total", "total t3", "t3 triiodothyronine", "triiodothyronine"],
                   "3053-6", "ng/dL", (20, 800), {"ng/dL": 1, "ng/mL": 100, "nmol/L": 65.1}, "LBXTT3"),
    "Total T4": _b(["t4", "t4 total", "total t4", "t4 thyroxine", "thyroxine"], "3026-2", "ug/dL", (0.5, 30), {"ug/dL": 1, "nmol/L": 1 / 12.87}, "LBXTT4"),
    "Anti-TPO": _b(["anti tpo", "tpo antibodies", "thyroid peroxidase antibodies", "anti thyroid peroxidase"], "8099-4", "IU/mL", (0, 10000), {"IU/mL": 1}, "LBXTPO"),
    # Vitamins
    "Vitamin D, 25-Hydroxy": _b(["vitamin d", "vitamin d 25 hydroxy", "25 hydroxy vitamin d", "vitamin d 25 oh", "25 oh vitamin d"],
                                "1989-3", "ng/mL", (2, 200), {"ng/mL": 1, "nmol/L": 1 / 2.496}, "LBXVIDMS"),
    "Vitamin B12": _b(["vitamin b12", "b12", "cobalamin"], "2132-9", "pg/mL", (50, 5000), {"pg/mL": 1, "pmol/L": 1.355}, "LBXB12"),
    "Folate": _b(["folate", "folic acid"], "2284-8", "ng/mL", (0.5, 50), {"ng/mL": 1, "nmol/L": 1 / 2.266}),
    # Iron studies
    "Iron": _b(["iron", "iron total"], "2498-4", "ug/dL", (5, 500), {"ug/dL": 1, "umol/L": 5.585}, "LBXSIR"),
    "Ferritin": _b(["ferritin"], "2276-4", "ng/mL", (1, 10000), {"ng/mL": 1, "ug/L": 1}, "LBXFER"),
    "Transferrin Saturation": _b(["transferrin saturation", "iron saturation", "tsat"], "2502-3", "%", (1, 100), PERCENT, "LBDPCT"),
    "TIBC": _b(["tibc", "iron binding capacity", "total iron binding capacity"], "2500-7", "ug/dL", (50, 700), {"ug/dL": 1, "umol/L": 5.585}, "LBDTIB"),
    "UIBC": _b(["uibc", "unsaturated iron binding capacity"], "2501-5", "ug/dL", (10, 600), {"ug/dL": 1, "umol/L": 5.585}, "LBXUIB"),
    "Transferrin": _b(["transferrin"], "3034-6", "mg/dL", (50, 600), {"mg/dL": 1, "g/L": 100}),
    # Inflammation and other
    "CRP": _b(["crp", "c reactive protein"], "1988-5", "mg/L", (0, 500), {"mg/L": 1, "mg/dL": 10}, "LBXCRP"),
    "hs-CRP": _b(["hs crp", "hscrp", "high sensitivity crp", "c reactive protein high sensitivity", "crp high sensitivity"],
                 "30522-7", "mg/L", (0, 500), {"mg/L": 1, "mg/dL": 10}, "LBXHSCRP"),
    "ESR": _b(["esr", "erythrocyte sedimentation rate", "sed rate"], "4537-7", "mm/hr", (0, 150), {"mm/hr": 1}),
    "Homocysteine": _b(["homocysteine"], "13965-9", "umol/L", (1, 200), {"umol/L": 1}, "LBXHCY"),
    "PSA": _b(["psa", "psa total", "prostate specific antigen", "psa prostate specific antigen total"], "2857-1", "ng/mL", (0, 10000), {"ng/mL": 1}),
}

# A required member is a canonical name or a tuple of alternatives (any one counts;
# the first is shown when none was found).
PANELS = {
    "cbc": {
        "name": "Complete Blood Count",
        "required": ["White Blood Cells", "Red Blood Cells", "Hemoglobin", "Hematocrit", "MCV", "MCH", "MCHC", "RDW", "Platelets"],
        "optional": ["MPV"],
        "section_keywords": ["complete blood count", "cbc", "hemogram"],
    },
    "differential": {
        "name": "WBC Differential",
        "required": ["Neutrophils %", "Lymphocytes %", "Monocytes %", "Eosinophils %", "Basophils %"],
        "optional": ["Neutrophils (Absolute)", "Lymphocytes (Absolute)", "Monocytes (Absolute)", "Eosinophils (Absolute)", "Basophils (Absolute)"],
        "section_keywords": ["differential"],
    },
    # CMP comes before BMP so a full CMP isn't also reported as a BMP, and `extends`
    # keeps a BMP from being reported as a partial CMP (see panels.detect_panels).
    "cmp": {
        "name": "Comprehensive Metabolic Panel",
        "extends": "bmp",
        "required": ["Glucose", "BUN", "Creatinine", "Sodium", "Potassium", "Chloride", "Carbon Dioxide", "Calcium",
                     "Total Protein", "Albumin", "Bilirubin, Total", "Alkaline Phosphatase", "AST", "ALT"],
        "optional": ["eGFR", "BUN/Creatinine Ratio", "Globulin", "Albumin/Globulin Ratio", "Anion Gap"],
        "section_keywords": ["comprehensive metabolic", "cmp"],
    },
    "bmp": {
        "name": "Basic Metabolic Panel",
        "required": ["Glucose", "BUN", "Creatinine", "Sodium", "Potassium", "Chloride", "Carbon Dioxide", "Calcium"],
        "optional": ["eGFR", "BUN/Creatinine Ratio", "Anion Gap"],
        "section_keywords": ["basic metabolic", "bmp"],
    },
    "lipid": {
        "name": "Lipid Panel",
        "required": ["Total Cholesterol", "HDL Cholesterol", "LDL Cholesterol", "Triglycerides"],
        "optional": ["VLDL Cholesterol", "Non-HDL Cholesterol", "Cholesterol/HDL Ratio", "LDL/HDL Ratio"],
        "section_keywords": ["lipid"],
    },
    "liver": {
        "name": "Liver Function",
        "required": ["Bilirubin, Total", "Bilirubin, Direct", "Alkaline Phosphatase", "AST", "ALT", "GGT", "Albumin"],
        "optional": ["Total Protein", "Bilirubin, Indirect", "Globulin", "Albumin/Globulin Ratio"],
        "section_keywords": ["liver", "hepatic"],
    },
    "kidney": {
        "name": "Kidney Function",
        "required": ["Creatinine", ("BUN", "Urea"), "eGFR"],
        "optional": ["Uric Acid", "BUN/Creatinine Ratio", "Phosphorus"],
        "section_keywords": ["kidney", "renal"],
    },
    "thyroid": {
        "name": "Thyroid Panel",
        "required": ["TSH", ("Free T4", "Total T4")],
        "optional": ["Free T3", "Total T3", "Anti-TPO"],
        "section_keywords": ["thyroid"],
    },
    "diabetes": {
        "name": "Diabetes Screening",
        "required": ["Glucose", "Hemoglobin A1c"],
        "optional": ["Estimated Average Glucose", "Insulin"],
        "section_keywords": ["hba1c", "glycosylated", "diabetes"],
    },
    "iron": {
        "name": "Iron Studies",
        "required": ["Iron", "TIBC", "Transferrin Saturation", "Ferritin"],
        "optional": ["UIBC", "Transferrin"],
        "section_keywords": ["iron"],
    },
    "vitamins": {
        "name": "Vitamins",
        "required": ["Vitamin D, 25-Hydroxy", "Vitamin B12", "Folate"],
        "optional": [],
        "section_keywords": ["vitamin"],
    },
    "inflammation": {
        "name": "Inflammation Markers",
        "required": [("CRP", "hs-CRP"), "ESR"],
        "optional": ["Homocysteine"],
        "section_keywords": ["inflammat", "sedimentation"],
    },
}
