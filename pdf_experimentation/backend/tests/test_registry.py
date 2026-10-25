import re

import pytest

from biomarkers import BIOMARKERS, PANELS
from lab_parser import _normalize_name
from units import normalize_unit


def loinc_check_digit(number):
    """LOINC's mod-10 check digit (the Luhn algorithm over the code's number part)."""
    total = 0
    for i, digit in enumerate(reversed(number)):
        d = int(digit) * (2 if i % 2 == 0 else 1)
        total += d // 10 + d % 10
    return (10 - total % 10) % 10


def test_no_alias_maps_to_two_biomarkers():
    owners = {}
    for name, biomarker in BIOMARKERS.items():
        for alias in biomarker["aliases"] + [name]:
            key = _normalize_name(alias)
            assert owners.setdefault(key, name) == name, f"{alias!r} is an alias of both {owners[key]} and {name}"


@pytest.mark.parametrize("name", BIOMARKERS)
def test_loinc_code_is_well_formed(name):
    code = BIOMARKERS[name]["loinc"]
    match = re.fullmatch(r"(\d{1,5})-(\d)", code)
    assert match, f"{name}: {code!r} isn't NNNNN-C"
    assert loinc_check_digit(match[1]) == int(match[2]), f"{name}: {code} fails the LOINC check digit"


@pytest.mark.parametrize("name", BIOMARKERS)
def test_conversions_use_normalized_units_and_include_canonical(name):
    biomarker = BIOMARKERS[name]
    for unit in biomarker["conversions"]:
        assert normalize_unit(unit) == unit, f"{name}: conversion unit {unit!r} isn't normalized"
    assert biomarker["conversions"].get(biomarker["unit"]) == 1, f"{name}: canonical unit must convert with factor 1"


@pytest.mark.parametrize("name", BIOMARKERS)
def test_plausible_range_is_ordered(name):
    low, high = BIOMARKERS[name]["plausible"]
    assert low < high


@pytest.mark.parametrize("panel_id", PANELS)
def test_panel_members_are_known_biomarkers(panel_id):
    panel = PANELS[panel_id]
    for member in panel["required"] + panel["optional"]:
        for name in member if isinstance(member, tuple) else (member,):
            assert name in BIOMARKERS, f"{panel_id}: unknown biomarker {name!r}"
