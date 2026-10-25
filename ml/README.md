# ml/

Notebooks for building training data and models for the per-panel analysis in
`backend/analysis.py`. They have their own environment, separate from the backend.

```sh
cd ml
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/jupyter lab notebooks/
```

Run the notebooks in order. The first run downloads about 35 MB of NHANES files into
`ml/data/nhanes/`. `ml/data/` and `ml/artifacts/` are git-ignored, so no row-level data
or trained models are committed.

| Notebook | What it does |
| --- | --- |
| `01_nhanes_dataset` | Downloads NHANES 2017–March 2020 (training) and August 2021–August 2023 (external validation), and checks every `nhanes` name in `backend/biomarkers.py` against the files and their units. It then converts values to the registry's canonical units, adds the values the app derives, and saves one table of adults per cycle. |
| `02_validate_formulas` | Runs the backend's eGFR, FIB-4, APRI and PhenoAge code on NHANES adults, using survey weights, and checks the results against known population patterns. |
| `03_train_liver_model` | A template trained model that predicts fatty liver (elastography CAP ≥ 285 dB/m) from the Liver panel plus age and sex. It is evaluated with calibration and subgroup checks, then exported with its metadata to `ml/artifacts/`. |
| `04_evaluate_liver_model` | Tests the saved liver model on held-out 2017–2020 adults and on the independent August 2021–August 2023 cycle. It covers AUROC with bootstrap intervals and calibration, against ALT alone and the published HSI/FLI scores. It also reports operating thresholds, subgroups, missing-test scenarios and input importance, and writes `evaluation.json` next to the model. |

| `05_liver_model_v2` | Builds the liver model the app uses. It adds BMI and metabolic labs, tunes by cross-validation and recalibrates on held-out participants. After evaluating it like notebook 04, it exports it to `backend/models/trained/liver_fatty_liver/v2/`. |

`nhanes.py` holds the shared download, registry-mapping and unit-conversion code, and
`evaluation.py` the survey-weighted metrics.

**scikit-learn version:** trained models are saved with `joblib` (pickle), so `ml/` and
`backend/` must use the same scikit-learn version. Both pin it.

**Data:** [NHANES](https://wwwn.cdc.gov/nchs/nhanes/) (CDC/NCHS), public domain.
Use the exam weights (`weight`, from `WTMECPRP`) for population estimates.

**A trained model's contract:** it receives the panel's `inputs` from `analysis.py`:
- the panel's tests, in `PANELS[panel]["inputs"]` order;
- canonical units;
- missing values as `None`/NaN;
- age and sex from the context.

Export it with the panel's `schema_version`, so the backend can refuse a model trained on
a different input layout.
