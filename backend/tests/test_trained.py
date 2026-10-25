import json
import shutil

import pytest
import sklearn

from models import PANEL_MODELS
from models.trained import TRAINED_DIR, IncompatibleModel, check_compatible, make_model, register_trained

LIVER_V2 = TRAINED_DIR / "liver_fatty_liver" / "v2"
METADATA = json.loads((LIVER_V2 / "metadata.json").read_text())

# Typical values in canonical units.
HEALTHY = {"ALT": 18, "AST": 20, "GGT": 15, "Alkaline Phosphatase": 70, "Bilirubin, Total": 0.6, "Albumin": 4.5,
           "Total Protein": 7.2, "Globulin": 2.7, "Albumin/Globulin Ratio": 1.67, "Triglycerides": 80,
           "HDL Cholesterol": 65, "Hemoglobin A1c": 5.1, "Platelets": 250, "Uric Acid": 4.5}
METABOLIC = {**HEALTHY, "ALT": 60, "AST": 38, "GGT": 70, "Triglycerides": 260, "HDL Cholesterol": 34, "Hemoglobin A1c": 6.4,
             "Uric Acid": 7.8}


def context(values, age=45, sex="male", bmi=None):
    return {"values": values, "patient": {"age": age, "sex": sex, "bmi": bmi}, "results": {}}


@pytest.fixture(scope="module")
def liver_model():
    return make_model(LIVER_V2)


def test_v2_is_registered_on_the_liver_panel():
    assert any(getattr(m, "__name__", "") == "nhanes-liver-v2" for m in PANEL_MODELS["liver"])


def test_risk_is_a_percentage_with_a_band(liver_model):
    out = liver_model(None, context(HEALTHY, bmi=22))
    assert out["unit"] == "%" and 0 <= out["value"] <= 100 and out["band"] in ("low", "intermediate", "high")
    assert out["model_version"] == "nhanes-liver-v2" and out["missing"] == []


def test_risk_rises_with_bmi_and_metabolic_labs(liver_model):
    lean = liver_model(None, context(HEALTHY, bmi=21))["value"]
    heavy = liver_model(None, context(HEALTHY, bmi=36))["value"]
    metabolic = liver_model(None, context(METABOLIC, bmi=36))["value"]
    assert lean < heavy < metabolic
    assert liver_model(None, context(HEALTHY, bmi=21))["band"] == "low"
    assert liver_model(None, context(METABOLIC, bmi=36))["band"] == "high"


def test_missing_bmi_still_estimates_and_says_so(liver_model):
    out = liver_model(None, context(HEALTHY))
    assert out["value"] is not None and "Adding height and weight" in out["interpretation"]


def test_required_inputs(liver_model):
    no_alt = {k: v for k, v in HEALTHY.items() if k != "ALT"}
    assert liver_model(None, context(no_alt))["missing"] == ["ALT"]
    out = liver_model(None, context(HEALTHY, age=None, sex=None))
    assert out["value"] is None and out["missing"] == ["age", "sex"] and out["interpretation"] == "Needs age, sex."


@pytest.mark.parametrize("change, message", [
    ({"panel_schema_version": 99}, "schema version"),
    ({"feature_units": {**METADATA["feature_units"], "ALT": "ukat/L"}}, "trained in ukat/L"),
    ({"features": METADATA["features"] + ["Not A Test"]}, "isn't a registry biomarker"),
    ({"sklearn_version": "0.1.0"}, "scikit-learn 0.1.0"),
])
def test_incompatible_models_are_refused(change, message):
    with pytest.raises(IncompatibleModel, match=message):
        check_compatible({**METADATA, **change}, sklearn.__version__)


def test_incompatible_model_is_skipped_not_registered(tmp_path):
    target = tmp_path / "liver_fatty_liver" / "v9"
    shutil.copytree(LIVER_V2, target)
    (target / "metadata.json").write_text(json.dumps({**METADATA, "panel_schema_version": 99}))
    registry = {}
    register_trained(registry, tmp_path)
    assert registry == {}
