"""Models that analysis.py runs: published formulas now, trained models later.

PANEL_MODELS maps a panel id to the models shown on that panel's analysis;
DEFAULT_REPORT_MODELS are models that use several panels at once. See the
MODELS comment in analysis.py for the call signature and output shape.
"""

PANEL_MODELS = {}
DEFAULT_REPORT_MODELS = []
