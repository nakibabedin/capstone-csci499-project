from biomarkers import BIOMARKERS, PANELS
from panels import derive, detect_panels, enrich, review_list


def result(canonical, value, unit=None, section=None, **extra):
    unit = unit if unit is not None else BIOMARKERS[canonical]["unit"]
    return {"test": canonical, "canonical": canonical, "value": value, "value_text": str(value),
            "unit": unit, "flag": None, "reference_range": None, "ref_low": None, "ref_high": None,
            "section": section, "page": 1, **extra}


CMP_VALUES = {
    "Glucose": 95, "BUN": 14, "Creatinine": 0.9, "Sodium": 140, "Potassium": 4.2, "Chloride": 102,
    "Carbon Dioxide": 25, "Calcium": 9.5, "Total Protein": 7.0, "Albumin": 4.4, "Bilirubin, Total": 0.6,
    "Alkaline Phosphatase": 70, "AST": 22, "ALT": 25,
}


def panels_of(results):
    return {p["id"]: p for p in detect_panels(derive(enrich(results)))}


def test_complete_cmp_is_not_also_bmp_liver_or_kidney():
    panels = panels_of([result(n, v) for n, v in CMP_VALUES.items()])
    assert list(panels) == ["cmp"]
    assert panels["cmp"]["status"] == "complete"


def test_bmp_alone_is_detected_as_bmp():
    bmp = PANELS["bmp"]["required"]
    panels = panels_of([result(n, CMP_VALUES[n]) for n in bmp])
    assert list(panels) == ["bmp"]
    assert panels["bmp"]["status"] == "complete"


def test_partial_panel_lists_missing_tests():
    panels = panels_of([result("Iron", 90), result("TIBC", 300), result("Transferrin Saturation", 30)])
    assert panels["iron"]["status"] == "partial"
    assert panels["iron"]["missing"] == ["Ferritin"]


def test_below_threshold_without_section_is_not_detected():
    assert "iron" not in panels_of([result("Iron", 90)])


def test_section_heading_detects_a_panel_below_threshold():
    panels = panels_of([result("Iron", 90, section="Iron Studies")])
    assert panels["iron"]["missing"] == ["TIBC", "Transferrin Saturation", "Ferritin"]


def test_alternatives_satisfy_a_required_member():
    panels = panels_of([result("Creatinine", 0.9), result("Urea", 30), result("eGFR", 95)])
    assert panels["kidney"]["status"] == "complete"


def test_differential_absolute_count_is_relabelled_by_unit():
    [r] = enrich([result("Neutrophils %", 7716, unit="/cmm")])
    assert r["canonical"] == "Neutrophils (Absolute)"
    assert r["value_std"] == 7.716


def test_implausible_value_is_suspect():
    results = enrich([result("Glucose", 9500)])
    assert results[0]["suspect"]


def test_derived_values():
    results = derive(enrich([
        result("Total Cholesterol", 200), result("HDL Cholesterol", 50),
        result("Total Protein", 7.0), result("Albumin", 4.0),
        result("Urea", 30), result("Creatinine", 1.0),
        result("Sodium", 140), result("Chloride", 104), result("Carbon Dioxide", 24),
    ]))
    derived = {r["canonical"]: r["value"] for r in results if r.get("derived")}
    assert derived == {
        "BUN": 14.01, "Non-HDL Cholesterol": 150, "Globulin": 3.0, "Albumin/Globulin Ratio": 1.33,
        "BUN/Creatinine Ratio": 14.01, "Anion Gap": 12,
    }


def test_reported_value_is_not_overwritten_by_derived():
    results = derive(enrich([result("Total Protein", 7.0), result("Albumin", 4.0), result("Globulin", 2.8)]))
    assert not any(r.get("derived") and r["canonical"] == "Globulin" for r in results)


def test_review_list_has_placeholders_for_missing_and_dedups_across_panels():
    results = derive(enrich([result(n, v) for n, v in CMP_VALUES.items()] + [result("Hemoglobin A1c", 5.4)]))
    panels = detect_panels(results)
    items = review_list(results, panels)
    names = [b["canonical"] for b in items]
    assert len(names) == len(set(names))
    glucose = next(b for b in items if b["canonical"] == "Glucose")
    assert glucose["panel"] == "cmp" and glucose["found"]
    assert all(b["found"] for b in items)  # CMP and diabetes are both complete
    assert {b["panel"] for b in items} == {"cmp", "diabetes"}


def test_word_answer_status():
    from status import result_status
    reactive, negative, group = enrich([
        {**result("HIV Ab/Ag", None, unit=""), "value_text": "Reactive"},
        {**result("Urine Protein", None, unit=""), "value_text": "Negative"},
        {**result("ABO Type", None, unit=""), "value_text": "O"},
    ])
    assert [result_status(r) for r in (reactive, negative, group)] == ["ABNORMAL", "normal", "unknown"]


def test_new_panels_are_detected_from_their_own_tests():
    found = {p["id"]: p for p in detect_panels(enrich([
        result("PT", 13.0), result("INR", 1.1),
        result("Testosterone", 500),
        result("CEA", 2.1),
        result("Amylase", 60),
    ]))}
    assert found["coagulation"]["missing"] == ["aPTT"]
    assert found["reproductive"]["status"] == "complete" and found["reproductive"]["found"] == ["Testosterone"]
    assert found["tumor_markers"]["found"] == ["CEA"]
    assert found["pancreas"]["missing"] == ["Lipase"]
    assert "cardiac" not in found and "adrenal" not in found
