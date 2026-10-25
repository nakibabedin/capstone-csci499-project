"""Models that analysis.py runs: published formulas and trained models.

PANEL_MODELS maps a panel id to the models shown on that panel's analysis;
DEFAULT_REPORT_MODELS are models that use several panels at once. See the
MODELS comment in analysis.py for the call signature and output shape.
Trained models are loaded from models/trained/ (see trained.py).
"""

from models.formulas import apri, egfr_ckd_epi_2021, fib4, mentzer_index, phenoage
from models.trained import register_trained

PANEL_MODELS = {
    "kidney": [egfr_ckd_epi_2021],
    "liver": [fib4, apri],
    "cbc": [mentzer_index],
}
DEFAULT_REPORT_MODELS = [phenoage]

register_trained(PANEL_MODELS)
