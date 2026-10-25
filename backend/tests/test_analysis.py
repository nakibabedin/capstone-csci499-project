import pytest

import analysis
from analysis import available_analyses
from biomarkers import PANELS
from panels import derive, enrich
from test_panels import CMP_VALUES, result


def analyses_of(results):
    return {a["id"]: a for a in available_analyses(derive(enrich(results)))}


def test_cmp_report_gets_every_panel_its_tests_cover():
    found = analyses_of([result(n, v) for n, v in CMP_VALUES.items()])
    assert set(found) == {"cmp", "bmp", "liver", "kidney"}
    # Glucose is shared with the BMP/CMP, so it alone doesn't produce a Diabetes analysis.
    assert "diabetes" not in found


def test_below_coverage_has_no_analysis():
    assert "cbc" not in analyses_of([result("Hemoglobin", 14), result("Platelets", 250)])


def test_inputs_follow_the_panel_order_with_none_for_missing():
    [thyroid] = available_analyses(enrich([result("TSH", 2.1), result("Free T4", 15.4, unit="pmol/L")]))
    values = thyroid["inputs"]["values"]
    assert list(values) == PANELS["thyroid"]["inputs"]
    assert values["TSH"] == 2.1 and values["Free T4"] == pytest.approx(1.2, abs=0.01) and values["Total T4"] is None
    assert thyroid["inputs"]["schema_version"] == PANELS["thyroid"]["schema_version"]
    assert "Total T4" in thyroid["inputs"]["missing"] and "TSH" not in thyroid["inputs"]["missing"]
    assert thyroid["coverage"] == pytest.approx(2 / len(values), abs=0.01)


def test_suspect_values_are_left_out_of_inputs_and_reported_as_findings():
    found = analyses_of([result("Hemoglobin A1c", 5.4), result("Insulin", 9000)])
    diabetes = found["diabetes"]
    assert diabetes["inputs"]["values"]["Insulin"] is None
    assert [f["test"] for f in diabetes["findings"]] == ["Insulin"] and diabetes["findings"][0]["suspect"]


def test_out_of_range_and_word_answers_are_encoded():
    found = analyses_of([
        {**result("Hemoglobin A1c", 7.1), "ref_high": 5.6},
        {**result("HBsAg", None, unit=""), "value_text": "Reactive"},
        {**result("ABO Type", None, unit=""), "value_text": "B"},
    ])
    diabetes, infection, group = found["diabetes"], found["infection"], found["blood_group"]
    assert diabetes["inputs"]["out_of_range"]["Hemoglobin A1c"] == 1
    assert [f["status"] for f in diabetes["findings"]] == ["high"]
    assert infection["inputs"]["values"]["HBsAg"] == 1 and infection["inputs"]["out_of_range"]["HBsAg"] == 1
    # A blood group is informational: present, but not a 0/1 health signal.
    assert group["inputs"]["values"]["ABO Type"] is None and group["findings"] == []


@pytest.mark.parametrize("results, panel_id, index, value", [
    ([result("Neutrophils %", 60), result("Lymphocytes %", 30), result("Monocytes %", 6),
      result("Eosinophils %", 3), result("Basophils %", 1)], "differential", "Neutrophil-to-lymphocyte ratio", 2.0),
    ([result("Triglycerides", 150), result("HDL Cholesterol", 50), result("Total Cholesterol", 200),
      result("LDL Cholesterol", 120)], "lipid", "Triglyceride-to-HDL ratio", 3.0),
    ([result("Triglycerides", 150), result("HDL Cholesterol", 50), result("Total Cholesterol", 200),
      result("LDL Cholesterol", 120)], "lipid", "Atherogenic index of plasma", 0.118),
    ([result("Glucose", 90), result("Hemoglobin A1c", 5.2), result("Insulin", 9)], "diabetes", "HOMA-IR", 2.0),
    ([result("Testosterone", 576.8), result("SHBG", 40)], "reproductive", "Free androgen index", 50.0),
    ([result("PSA", 4.0), result("Free PSA", 1.0)], "tumor_markers", "Free PSA percentage", 25.0),
    ([result("Iron", 100), result("TIBC", 400), result("Ferritin", 80)], "iron", "Transferrin saturation (calculated)", 25.0),
])
def test_indices(results, panel_id, index, value):
    indices = {i["name"]: i["value"] for i in analyses_of(results)[panel_id]["indices"]}
    assert indices[index] == pytest.approx(value, abs=0.01)


def test_index_is_skipped_without_its_inputs():
    diabetes = analyses_of([result("Glucose", 90), result("Hemoglobin A1c", 5.2)])["diabetes"]
    assert diabetes["indices"] == []


def test_registered_model_output_is_included(monkeypatch):
    monkeypatch.setitem(analysis.MODELS, "thyroid", lambda inputs: {"prediction": inputs["values"]["TSH"] * 2, "model_version": "test"})
    monkeypatch.setitem(analysis.MODELS, "allergy", lambda inputs: 1 / 0)
    found = analyses_of([result("TSH", 2.0), result("IgE", 50)])
    assert found["thyroid"]["model"] == {"prediction": 4.0, "model_version": "test"}
    assert "error" in found["allergy"]["model"]
    assert analyses_of([result("TSH", 2.0)])["thyroid"]["model"] == {"prediction": 4.0, "model_version": "test"}
