"""Result rows as they appear in real reports, through parsing and enrichment."""

import pytest

from lab_parser import parse_result_line
from panels import enrich


@pytest.mark.parametrize("line, canonical, value_std, unit_std", [
    ("WBC Count H 10570 /cmm 4000 - 10000", "White Blood Cells", 10.57, "10^3/uL"),
    ("RBC Count 4.79 million/cmm 4.5 - 5.5", "Red Blood Cells", 4.79, "10^6/uL"),
    ("Platelet Count 150000 /cmm 150000 - 410000", "Platelets", 150.0, "10^3/uL"),
    ("Fasting Blood Sugar H 141.0 mg/dL 74 - 106", "Glucose", 141.0, "mg/dL"),
    ("Iron 103.00 micro g/dL 49 - 181", "Iron", 103.0, "ug/dL"),
    ("TSH - Thyroid Stimulating Hormone 0.8199 microIU/mL 0.35 - 4.94", "TSH", 0.8199, "uIU/mL"),
    ("T3 - Triiodothyronine 1.01 ng/mL 0.58 - 1.59", "Total T3", 101.0, "ng/dL"),
    ("Conjugated Bilirubin 0.30 mg/dL 0.0 - 0.3", "Bilirubin, Direct", 0.3, "mg/dL"),
    ("Mean Blood Glucose 157.07 mg/dL", "Estimated Average Glucose", 157.07, "mg/dL"),
    ("Glucose 5.4 mmol/L 3.9-5.5", "Glucose", 97.29, "mg/dL"),
    ("Hemoglobin 145 g/L 130-170", "Hemoglobin", 14.5, "g/dL"),
])
def test_parsed_row_is_converted(line, canonical, value_std, unit_std):
    [r] = enrich(parse_result_line(line))
    assert r["canonical"] == canonical
    assert r["value_std"] == pytest.approx(value_std, abs=0.01)
    assert r["unit_std"] == unit_std
    assert not r["suspect"]


def test_differential_row_yields_percent_and_absolute():
    results = enrich(parse_result_line("Neutrophils 73 % 40 - 80 7716 /cmm 2000 - 6700"))
    assert [(r["canonical"], r["value_std"]) for r in results] == [
        ("Neutrophils %", 73.0),
        ("Neutrophils (Absolute)", 7.716),
    ]
