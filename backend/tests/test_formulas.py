"""The published formulas, checked against hand-worked examples."""

import pytest

from models.formulas import apri, egfr_ckd_epi_2021, fib4, mentzer_index, phenoage


def context(values, age=None, sex=None, results=None):
    return {"values": values, "patient": {"age": age, "sex": sex}, "results": results or {}}


@pytest.mark.parametrize("creatinine, age, sex, expected, category", [
    # 142 × (1.0/0.9)^-1.2 × 0.9938^50
    (1.0, 50, "male", 91.70, "G1"),
    # 142 × (0.8/0.7)^-1.2 × 0.9938^60 × 1.012
    (0.8, 60, "female", 84.30, "G2"),
    # 142 × (0.6/0.7)^-0.241 × 0.9938^30 × 1.012 = 142 × 1.0379 × 0.8298 × 1.012, below κ so α applies
    (0.6, 30, "female", 123.76, "G1"),
    # 142 × (2.5/0.9)^-1.2 × 0.9938^70 = 142 × 0.2935 × 0.6471
    (2.5, 70, "male", 26.96, "G4"),
])
def test_egfr(creatinine, age, sex, expected, category):
    out = egfr_ckd_epi_2021(None, context({"Creatinine": creatinine}, age, sex))
    assert out["value"] == pytest.approx(expected, abs=0.05)
    assert out["unit"] == "mL/min/1.73m2" and category in out["interpretation"]


def test_egfr_needs_age_and_sex_and_skips_children():
    out = egfr_ckd_epi_2021(None, context({"Creatinine": 1.0}, age=40))
    assert out["value"] is None and out["missing"] == ["sex"] and out["interpretation"] == "Needs sex."
    assert egfr_ckd_epi_2021(None, context({"Creatinine": 0.5}, age=12, sex="male")) is None


@pytest.mark.parametrize("age, ast, alt, platelets, expected, band", [
    (50, 30, 25, 250, 1.2, "unlikely"),       # 50 × 30 / (250 × 5)
    (70, 30, 25, 250, 1.68, "unlikely"),      # 1.68 is under the age-65 cutoff of 2.0
    (60, 90, 36, 120, 7.5, "likely; follow-up"),
    (45, 40, 25, 200, 1.8, "indeterminate"),
])
def test_fib4(age, ast, alt, platelets, expected, band):
    out = fib4(None, context({"AST": ast, "ALT": alt, "Platelets": platelets}, age))
    assert out["value"] == pytest.approx(expected, abs=0.01) and band in out["interpretation"]


def test_fib4_flags_young_patients():
    out = fib4(None, context({"AST": 30, "ALT": 25, "Platelets": 250}, age=28))
    assert "less reliable under age 35" in out["interpretation"]


def test_apri_uses_the_reports_upper_limit_when_printed():
    values = {"AST": 80, "Platelets": 100}
    assumed = apri(None, context(values))
    assert assumed["value"] == pytest.approx(2.0) and "assumed" in assumed["interpretation"] and "likely" in assumed["interpretation"]
    printed = apri(None, context(values, results={"AST": {"ref_high": 32, "unit": "IU/L"}}))
    assert printed["value"] == pytest.approx(2.5) and "(32 U/L)" in printed["interpretation"]


def test_mentzer_only_for_small_red_cells():
    out = mentzer_index(None, context({"MCV": 70, "Red Blood Cells": 5.8}))
    assert out["value"] == pytest.approx(12.07, abs=0.01) and "thalassemia trait" in out["interpretation"]
    assert "iron deficiency" in mentzer_index(None, context({"MCV": 72, "Red Blood Cells": 4.0}))["interpretation"]
    assert mentzer_index(None, context({"MCV": 90, "Red Blood Cells": 4.8})) is None


HEALTHY_40 = {
    "Albumin": 4.6, "Creatinine": 0.9, "Glucose": 88, "CRP": 0.8, "Lymphocytes %": 32, "MCV": 89,
    "RDW": 12.6, "Alkaline Phosphatase": 65, "White Blood Cells": 5.8,
}


def test_phenoage_is_close_to_age_for_healthy_labs_and_older_for_unhealthy_ones():
    healthy = phenoage(None, context(HEALTHY_40, age=40))
    # Optimal labs put PhenoAge below chronological age.
    assert 25 < healthy["value"] < 40 and healthy["unit"] == "years" and "younger" in healthy["interpretation"]
    unhealthy = phenoage(None, context({**HEALTHY_40, "Albumin": 3.4, "Glucose": 160, "CRP": 25, "RDW": 16.5, "White Blood Cells": 11}, age=40))
    assert unhealthy["value"] > healthy["value"] + 10 and "older than actual age (40)" in unhealthy["interpretation"]


def test_phenoage_uses_hs_crp_and_lists_what_is_missing():
    values = {**HEALTHY_40, "hs-CRP": HEALTHY_40["CRP"]}
    del values["CRP"]
    assert phenoage(None, context(values, age=40))["value"] == phenoage(None, context(HEALTHY_40, age=40))["value"]
    out = phenoage(None, context({"Albumin": 4.6}, age=None))
    assert out["value"] is None and out["missing"][:2] == ["Creatinine", "Glucose"] and out["missing"][-1] == "age"
