"""Download NHANES files and map them onto the backend's biomarker registry.

NHANES (https://wwwn.cdc.gov/nchs/nhanes/) publishes one SAS transport file per
component per cycle, keyed by participant id SEQN. The registry in
backend/biomarkers.py records each biomarker's NHANES variable (`nhanes`); this
module checks those names against the files and converts values to the
registry's canonical units, using the unit NHANES prints in each variable's label.

Downloads are cached in ml/data/nhanes/, which git ignores.
"""

import re
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data" / "nhanes"
sys.path.insert(0, str(ML_DIR.parent / "backend"))

from biomarkers import BIOMARKERS  # noqa: E402
from units import normalize_unit  # noqa: E402

URL = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{name}.xpt"

# The 2017–March 2020 pre-pandemic cycle (file prefix P_): lab panels, demographics,
# body measures and liver elastography.
PRE_PANDEMIC = {
    "year": 2017,
    "files": ["P_DEMO", "P_CBC", "P_BIOPRO", "P_HSCRP", "P_GHB", "P_GLU", "P_INS", "P_TCHOL", "P_HDL",
              "P_TRIGLY", "P_FERTIN", "P_FETIB", "P_HEPBD", "P_HEPC", "P_ALB_CR", "P_TST", "P_BMX", "P_LUX"],
}

# NHANES unit spellings units.normalize_unit doesn't know.
NHANES_UNITS = {
    "1000 cells/ul": "10^3/uL", "1000 cells/µl": "10^3/uL", "1000 cell/ul": "10^3/uL", "million cells/ul": "10^6/uL", "million cells/µl": "10^6/uL",
    "uu/ml": "uIU/mL", "µu/ml": "uIU/mL", "uiu/ml": "uIU/mL", "miu/l": "uIU/mL",
    "ng/ml": "ng/mL", "ug/dl": "ug/dL", "µg/dl": "ug/dL", "mg/l": "mg/L", "mg/dl": "mg/dL", "g/dl": "g/dL",
    "iu/l": "IU/L", "u/l": "U/L", "fl": "fL", "pg": "pg", "%": "%", "mmol/l": "mmol/L",
}


# Variables NHANES stores as answer codes rather than values, mapped to the 0/1
# encoding analysis.py gives word answers (1 = abnormal).
CODED = {
    "LBDHBG": {1: 1, 2: 0},  # Hepatitis B surface antigen: 1 positive, 2 negative
}


def download(name, year):
    """The local path of an NHANES file, downloading it on first use."""
    path = DATA_DIR / f"{name}.xpt"
    if not path.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL.format(year=year, name=name), path)
    return path


def load_file(name, year):
    """(DataFrame, {column: label}) for one file."""
    # Labels are Latin-1 ("µ" is byte 0xB5).
    df, meta = pyreadstat.read_xport(download(name, year), encoding="latin1")
    return df, meta.column_names_to_labels


def load_cycle(cycle=PRE_PANDEMIC):
    """All of a cycle's files joined on SEQN (everyone in DEMO, NaN where a file has no row),
    plus every column's label."""
    merged, labels = None, {}
    for name in cycle["files"]:
        df, file_labels = load_file(name, cycle["year"])
        labels.update({col: (name, label) for col, label in file_labels.items() if col != "SEQN"})
        merged = df if merged is None else merged.merge(df, on="SEQN", how="left", suffixes=("", f"_{name}"))
    return merged, labels


def label_unit(label):
    """The unit at the end of an NHANES label: 'Albumin, refrigerated serum (g/dL)' -> 'g/dL'."""
    match = re.search(r"\(([^()]*)\)\s*$", label or "")
    if not match:
        return None
    raw = match.group(1).strip()
    return NHANES_UNITS.get(raw.lower(), normalize_unit(raw))


def registry_mapping(labels):
    """One row per registry biomarker that names an NHANES variable: whether the variable
    is in these files, its label and unit, and the factor to the registry's canonical unit."""
    rows = []
    for canonical, biomarker in BIOMARKERS.items():
        var = biomarker["nhanes"]
        if not var:
            continue
        file, label = labels.get(var, (None, None))
        unit = label_unit(label)
        conversion = biomarker["conversions"].get(unit) if unit else None
        if conversion is None and unit is None and biomarker["unit"] is None:
            conversion = biomarker["conversions"].get(None)
        if var in CODED and file is not None:
            unit, conversion = "coded answer", 1
        rows.append({
            "biomarker": canonical,
            "nhanes": var,
            "file": file,
            "label": label,
            "nhanes_unit": unit,
            "registry_unit": biomarker["unit"],
            "factor": conversion if not isinstance(conversion, tuple) else None,
            "status": ("not in these files" if file is None
                       else "ok" if conversion is not None
                       else f"unit {unit!r} has no conversion"),
        })
    return pd.DataFrame(rows)


def to_registry(df, mapping):
    """The mapped biomarkers as columns named and scaled like the registry (canonical units)."""
    usable = mapping[mapping["status"] == "ok"]
    return pd.DataFrame({
        row.biomarker: df[row.nhanes].map(CODED[row.nhanes]) if row.nhanes in CODED else df[row.nhanes] * row.factor
        for row in usable.itertuples()
    }, index=df.index)


def add_derived(values):
    """Fill values the app derives when a report leaves them out (Non-HDL, Globulin, ...),
    using the backend's own formulas (panels.DERIVATIONS), so training data matches what
    models see from a parsed report."""
    from panels import DERIVATIONS

    values = values.copy()
    for name, (inputs, formula) in DERIVATIONS.items():
        if not all(i in values for i in inputs):
            continue
        if name not in values:
            values[name] = np.nan
        todo = values[name].isna() & values[inputs].notna().all(axis=1)
        derived = [formula(*row) for row in values.loc[todo, inputs].itertuples(index=False)]
        values.loc[todo, name] = [np.nan if v is None else round(v, 2) for v in derived]
    return values


def demographics(df):
    """Age (years), sex ('male'/'female') and the exam weights, from DEMO."""
    return pd.DataFrame({
        "age": df["RIDAGEYR"],
        "sex": df["RIAGENDR"].map({1: "male", 2: "female"}),
        "race_ethnicity": df["RIDRETH3"].map({1: "Mexican American", 2: "Other Hispanic", 3: "Non-Hispanic White",
                                              4: "Non-Hispanic Black", 6: "Non-Hispanic Asian", 7: "Other/Multiracial"}),
        # Exam weights for the pre-pandemic cycle; use them for population estimates.
        "weight": df["WTMECPRP"],
    }, index=df.index)
