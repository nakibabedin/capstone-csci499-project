"""Trained models exported by the ml/ notebooks, run as analysis models.

Each model lives in models/trained/<name>/<version>/ as model.joblib (a scikit-learn
classifier) and metadata.json, which records everything needed to use it safely:
the panel it belongs to, its features in order and their registry units, Platt
calibration, risk-band thresholds and its validation metrics.

A model is only loaded if it still fits the registry: the panel's schema version,
each feature's canonical unit and the scikit-learn version must all match what it
was trained with. Otherwise it's skipped with a warning rather than giving wrong
answers silently.
"""

import json
import logging
import math
import warnings
from pathlib import Path

from biomarkers import BIOMARKERS, PANELS

log = logging.getLogger(__name__)

TRAINED_DIR = Path(__file__).resolve().parent / "trained"

# Features that come from the patient rather than the report, and the name to show when missing.
PATIENT_FEATURES = {"age": "age", "male": "sex", "bmi": "height and weight"}


class IncompatibleModel(Exception):
    pass


def check_compatible(metadata, sklearn_version):
    """Raise IncompatibleModel if the model no longer fits the registry or this scikit-learn."""
    panel = PANELS.get(metadata["panel"])
    if panel is None:
        raise IncompatibleModel(f"unknown panel {metadata['panel']!r}")
    if metadata["panel_schema_version"] != panel["schema_version"]:
        raise IncompatibleModel(f"trained for {metadata['panel']} schema version {metadata['panel_schema_version']}, "
                                f"registry is at {panel['schema_version']}")
    for feature in metadata["features"]:
        if feature in PATIENT_FEATURES:
            continue
        if feature not in BIOMARKERS:
            raise IncompatibleModel(f"feature {feature!r} isn't a registry biomarker")
        if BIOMARKERS[feature]["unit"] != metadata["feature_units"].get(feature):
            raise IncompatibleModel(f"{feature} was trained in {metadata['feature_units'].get(feature)}, "
                                    f"registry now uses {BIOMARKERS[feature]['unit']}")
    if metadata["sklearn_version"] != sklearn_version:
        raise IncompatibleModel(f"saved with scikit-learn {metadata['sklearn_version']}, running {sklearn_version}")


def _feature_row(metadata, context):
    """The model's input row from the report's canonical values and the patient, plus what
    required inputs are missing (as names to show the user)."""
    values, patient = context["values"], context["patient"]
    sex = patient.get("sex")
    row = {
        **{f: values.get(f) for f in metadata["features"] if f not in PATIENT_FEATURES},
        "age": patient.get("age"),
        "male": None if sex is None else int(sex == "male"),
        "bmi": patient.get("bmi"),
    }
    missing = [PATIENT_FEATURES.get(f, f) for f in metadata["required"] if row.get(f) is None]
    return [math.nan if row.get(f) is None else row[f] for f in metadata["features"]], missing


def _band(risk, thresholds):
    if risk < thresholds["low_below"]:
        return "low"
    return "high" if risk >= thresholds["high_from"] else "intermediate"


def make_model(directory):
    """A (inputs, context) -> output model for one exported directory."""
    import joblib
    import sklearn

    metadata = json.loads((directory / "metadata.json").read_text())
    check_compatible(metadata, sklearn.__version__)
    classifier = joblib.load(directory / "model.joblib")
    platt = metadata["calibration"]

    def run(inputs, context):
        row, missing = _feature_row(metadata, context)
        if missing:
            return {"name": metadata["name"], "value": None, "unit": "%", "interpretation": "Needs " + ", ".join(missing) + ".",
                    "model_version": metadata["model_version"], "missing": missing}
        with warnings.catch_warnings():
            # Trained on a DataFrame; a plain row in the same order is equivalent.
            warnings.filterwarnings("ignore", message="X does not have valid feature names")
            p = float(classifier.predict_proba([row])[0][1])
        p = min(max(p, 1e-6), 1 - 1e-6)
        risk = 1 / (1 + math.exp(-(platt["coef"] * math.log(p / (1 - p)) + platt["intercept"])))
        band = _band(risk, metadata["thresholds"])
        interpretation = (
            f"{band.capitalize()} estimated chance of excess liver fat (as a liver scan would show), "
            "from liver and metabolic tests, age, sex and BMI."
        )
        if context["patient"].get("bmi") is None:
            interpretation += " Adding height and weight makes this estimate much more accurate."
        interpretation += " A screening estimate from a model trained on US survey data, not a diagnosis."
        return {"name": metadata["name"], "value": round(100 * risk), "unit": "%", "interpretation": interpretation,
                "model_version": metadata["model_version"], "missing": [], "band": band}

    run.__name__ = metadata["model_version"]
    run.metadata = metadata
    return run


def register_trained(panel_models, directory=TRAINED_DIR):
    """Add every compatible trained model under `directory` to panel_models[panel]."""
    for metadata_path in sorted(directory.glob("*/*/metadata.json")):
        try:
            model = make_model(metadata_path.parent)
        except ImportError as e:
            log.warning("Skipping trained models: %s", e)
            return
        except (IncompatibleModel, OSError, KeyError, ValueError) as e:
            log.warning("Skipping trained model %s: %s", metadata_path.parent, e)
            continue
        panel_models.setdefault(model.metadata["panel"], []).append(model)
