"""Unit normalization and conversion to each biomarker's canonical unit.

Labs spell the same unit many ways ("/cmm", "cells/µL", "K/uL", "x10³/µL"), and
regions use different units for the same test (glucose in mg/dL or mmol/L).
normalize_unit() maps spellings to one form; to_canonical() converts a value to
its biomarker's canonical unit, and returns None rather than guessing when the
unit isn't one the biomarker lists.
"""

from biomarkers import BIOMARKERS

# Lowercased, µ/mc -> u spellings -> normalized unit.
UNIT_SPELLINGS = {
    # Cell counts per microlitre
    "/ul": "/uL", "/cmm": "/uL", "/cumm": "/uL", "/mm3": "/uL", "cells/ul": "/uL", "cells/cmm": "/uL", "cells/cumm": "/uL",
    "10^3/ul": "10^3/uL", "x10^3/ul": "10^3/uL", "10*3/ul": "10^3/uL", "x10e3/ul": "10^3/uL", "10e3/ul": "10^3/uL",
    "k/ul": "10^3/uL", "thou/ul": "10^3/uL", "thou/cmm": "10^3/uL", "thousand/ul": "10^3/uL", "10^3/cmm": "10^3/uL",
    "10^9/l": "10^9/L", "x10^9/l": "10^9/L", "10*9/l": "10^9/L",
    "10^6/ul": "10^6/uL", "x10^6/ul": "10^6/uL", "10*6/ul": "10^6/uL", "x10e6/ul": "10^6/uL", "10e6/ul": "10^6/uL",
    "m/ul": "10^6/uL", "mil/ul": "10^6/uL", "million/ul": "10^6/uL", "million/cmm": "10^6/uL", "mill/cmm": "10^6/uL",
    "million/cumm": "10^6/uL", "10^6/cmm": "10^6/uL",
    "10^12/l": "10^12/L", "x10^12/l": "10^12/L", "10*12/l": "10^12/L",
    "lakh/cmm": "10^5/uL", "lakhs/cmm": "10^5/uL", "lakh/cumm": "10^5/uL", "lakhs/cumm": "10^5/uL", "lakh/ul": "10^5/uL",
    # Mass and molar concentrations
    "mg/dl": "mg/dL", "g/dl": "g/dL", "gm/dl": "g/dL", "gms/dl": "g/dL", "ug/dl": "ug/dL", "ng/dl": "ng/dL",
    "g/l": "g/L", "mg/l": "mg/L", "ug/l": "ug/L", "ng/ml": "ng/mL", "pg/ml": "pg/mL",
    "mmol/l": "mmol/L", "umol/l": "umol/L", "nmol/l": "nmol/L", "pmol/l": "pmol/L", "meq/l": "mEq/L",
    "mmol/mol": "mmol/mol", "l/l": "L/L",
    # Activity
    "u/l": "U/L", "iu/l": "IU/L", "iu/ml": "IU/mL",
    "uiu/ml": "uIU/mL", "uu/ml": "uIU/mL", "miu/l": "uIU/mL",
    # Other
    "%": "%", "fl": "fL", "pg": "pg",
    "mm/hr": "mm/hr", "mm/h": "mm/hr", "mm/1hr": "mm/hr", "mm/1st hr": "mm/hr", "mm/1sthr": "mm/hr",
    "ml/min/1.73m2": "mL/min/1.73m2", "ml/min/1.73m^2": "mL/min/1.73m2", "ml/min/1.73": "mL/min/1.73m2",
}


def normalize_unit(token):
    """The normalized spelling of a unit, or the token unchanged if it isn't recognized."""
    if token is None:
        return None
    key = token.strip().lower().replace("µ", "u").replace("μ", "u").replace("³", "^3").replace("⁶", "^6")
    key = key.replace("micro", "u").replace("mcg", "ug")
    return UNIT_SPELLINGS.get(key, token)


def to_canonical(canonical, value, unit):
    """(value, unit) converted to the biomarker's canonical unit, or (None, None)
    if the biomarker is unknown or doesn't list a conversion for the unit."""
    biomarker = BIOMARKERS.get(canonical)
    if biomarker is None or value is None:
        return None, None
    conversion = biomarker["conversions"].get(normalize_unit(unit))
    if conversion is None:
        return None, None
    factor, offset = conversion if isinstance(conversion, tuple) else (conversion, 0)
    return round(value * factor + offset, 4), biomarker["unit"]
