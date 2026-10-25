import pytest

from units import normalize_unit, to_canonical


@pytest.mark.parametrize("token, expected", [
    ("/cmm", "/uL"), ("cells/µL", "/uL"), ("/cumm", "/uL"),
    ("K/uL", "10^3/uL"), ("thou/uL", "10^3/uL"), ("x10³/µL", "10^3/uL"), ("10^3/uL", "10^3/uL"),
    ("million/cmm", "10^6/uL"), ("M/uL", "10^6/uL"), ("10^12/L", "10^12/L"),
    ("lakhs/cmm", "10^5/uL"),
    ("mg/dl", "mg/dL"), ("gm/dL", "g/dL"), ("µg/dL", "ug/dL"), ("mcg/dL", "ug/dL"), ("microg/dL", "ug/dL"),
    ("micromol/L", "umol/L"), ("mmol/L", "mmol/L"), ("mEq/L", "mEq/L"),
    ("microIU/mL", "uIU/mL"), ("mIU/L", "uIU/mL"),
    ("mm/1hr", "mm/hr"), ("FL", "fL"),
    ("mIU/mL", "mIU/mL"), ("S/Co", "S/CO"), ("COI", "index"), ("Seconds", "sec"), ("ng/L", "ng/L"), ("U/mL", "U/mL"), ("cells/hpf", "/hpf"),
    (None, None),
    ("mOsm/kg", "mOsm/kg"),  # unrecognized -> unchanged
])
def test_normalize_unit(token, expected):
    assert normalize_unit(token) == expected


@pytest.mark.parametrize("canonical, value, unit, expected", [
    ("White Blood Cells", 10570, "/cmm", (10.57, "10^3/uL")),
    ("White Blood Cells", 6.2, "K/uL", (6.2, "10^3/uL")),
    ("Platelets", 2.5, "lakhs/cmm", (250.0, "10^3/uL")),
    ("Red Blood Cells", 4.79, "million/cmm", (4.79, "10^6/uL")),
    ("Hemoglobin", 145, "g/L", (14.5, "g/dL")),
    ("Glucose", 5.5, "mmol/L", (99.088, "mg/dL")),
    ("Total Cholesterol", 5.0, "mmol/L", (193.35, "mg/dL")),
    ("Creatinine", 88.4, "µmol/L", (1.0, "mg/dL")),
    ("Total T3", 1.01, "ng/mL", (101.0, "ng/dL")),
    ("Hemoglobin A1c", 53, "mmol/mol", (7.0, "%")),
    ("Cholesterol/HDL Ratio", 3.1, None, (3.1, None)),
])
def test_to_canonical(canonical, value, unit, expected):
    value_std, unit_std = to_canonical(canonical, value, unit)
    assert unit_std == expected[1]
    assert value_std == pytest.approx(expected[0], abs=0.01)


@pytest.mark.parametrize("canonical, value, unit", [
    ("Total T4", 7.84, "mg/mL"),       # a lab typo: never guess
    ("TIBC", 352, None),               # no unit printed
    ("Glucose", 100, "g/dL"),          # a real unit, but not one glucose is reported in
    ("Not A Biomarker", 1, "mg/dL"),
    ("Glucose", None, "mg/dL"),
])
def test_to_canonical_refuses_unknown(canonical, value, unit):
    assert to_canonical(canonical, value, unit) == (None, None)
