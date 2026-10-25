import pytest

from lab_parser import extract_patient


@pytest.mark.parametrize("lines, age, sex", [
    (["Sex/Age : Male / 41 Y 01-Feb-1982"], 41, "male"),
    (["Age/Sex: 35 Yrs / F"], 35, "female"),
    (["Patient Name: A. Person", "Age : 62 Years", "Gender : Female"], 62, "female"),
    (["Age: 8 Months Sex: M"], 0.7, "male"),
    (["Gender : Male"], None, "male"),
    (["Age : 150 Years"], None, None),  # implausible
    (["Registration on : 20-Feb-2023 09:10", "Hemoglobin 14.5 g/dL 13.0 - 16.5"], None, None),
])
def test_extract_patient(lines, age, sex):
    patient = extract_patient([lines])
    assert (patient["age"], patient["sex"]) == (age, sex)


def test_first_page_with_both_wins():
    patient = extract_patient([["Age : 41 Years"], ["Sex : Female"], ["Age : 99 Years", "Sex : Male"]])
    assert (patient["age"], patient["sex"], patient["source"]) == (41, "female", "Age : 41 Years")
