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


@pytest.mark.parametrize("line, canonical, value_std, unit_std", [
    ("PT 13.2 sec 11.0 - 13.5", "PT", 13.2, "sec"),
    ("INR 1.10 0.8 - 1.2", "INR", 1.1, None),
    ("APTT 31.5 seconds 25 - 35", "aPTT", 31.5, "sec"),
    ("HS-Troponin I 4.2 ng/L <19.8", "hs-Troponin I", 4.2, "ng/L"),
    ("Troponin I 0.02 ng/mL <0.04", "Troponin I", 0.02, "ng/mL"),
    ("NT-proBNP 85 pg/mL <125", "NT-proBNP", 85.0, "pg/mL"),
    ("LH 6.2 mIU/mL 1.7 - 8.6", "LH", 6.2, "mIU/mL"),
    ("Testosterone Total 15.6 nmol/L 8.6 - 29", "Testosterone", 449.9, "ng/dL"),
    ("Cortisol (AM) 410 nmol/L 166 - 507", "Cortisol", 14.86, "ug/dL"),
    ("CA 19-9 12.4 U/mL <37", "CA 19-9", 12.4, "U/mL"),
    ("Apo B 0.95 g/L 0.6 - 1.2", "Apolipoprotein B", 95.0, "mg/dL"),
    ("HBsAg 0.290 S/Co Non Reactive : <1.0", "HBsAg", 0.29, "S/CO"),
    ("Hb A L 84.4 % 96.8 - 97.8", "Hb A", 84.4, "%"),
])
def test_new_panel_rows_are_converted(line, canonical, value_std, unit_std):
    [r] = enrich(parse_result_line(line))
    assert r["canonical"] == canonical
    assert r["value_std"] == pytest.approx(value_std, abs=0.01)
    assert r["unit_std"] == unit_std
    assert not r["suspect"]


@pytest.mark.parametrize("line, canonical, value_text, reference, text_status", [
    ('ABO Type "A"', "ABO Type", '"A"', None, None),
    ("Rh (D) Type Positive", "Rh Type", "Positive", None, None),
    ("Blood Group B Positive", "Blood Group", "B Positive", None, None),
    ("Colour Pale Yellow Pale Yellow", "Urine Colour", "Pale Yellow", "Pale Yellow", "normal"),
    ("Urine Glucose Present (+) Absent", "Urine Glucose", "Present (+)", "Absent", "abnormal"),
    ("Urine Ketone Absent Absent", "Urine Ketones", "Absent", "Absent", "normal"),
    ("Leukocyte Esterase 2+ Negative", "Leukocyte Esterase", "2+", "Negative", "abnormal"),
    ("HIV I & II Antibodies Non Reactive", "HIV Ab/Ag", "Non Reactive", None, "normal"),
    ("Anti HCV Reactive Non Reactive", "Anti-HCV", "Reactive", "Non Reactive", "abnormal"),
    ("VDRL -ve", "Syphilis (RPR/VDRL)", "-ve", None, "normal"),
    ("Casts Absent /hpf Absent", None, None, None, None),  # casts aren't a registry test
    ("Epithelial Cells Occasional /hpf", "Epithelial Cells", "Occasional", None, "normal"),
])
def test_word_answer_rows(line, canonical, value_text, reference, text_status):
    results = enrich(parse_result_line(line))
    if canonical is None:
        assert results == []
        return
    [r] = results
    assert (r["canonical"], r["value_text"], r["reference_range"], r["text_status"]) == (canonical, value_text, reference, text_status)
    assert r["value"] is None and not r["suspect"]


def test_cell_count_range_is_compared_by_upper_end():
    [r] = enrich(parse_result_line("Pus Cells 3-5 /hpf 0 - 5"))
    assert (r["canonical"], r["value"], r["value_text"], r["ref_high"]) == ("Pus Cells", 5.0, "3-5", 5.0)


@pytest.mark.parametrize("line", [
    "Interpretation Non Reactive",
    "Parasites Malarial parasite is not detected.",
    "must be verified by confirmatory WESTERN BLOT before declaring the patient positive",
    "HBsAg Non Reactive but repeat testing is advised",
    "Nitrite Absent Absent Absent Absent Absent",
    "Bilirubin Absent Absent",  # blood bilirubin takes no word answers
])
def test_prose_and_unknown_words_are_not_results(line):
    assert parse_result_line(line) == []
