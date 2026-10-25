import re

import pytest

from biomarkers import BIOMARKERS, PANELS, normalize_answer
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


NUMERIC = [name for name, b in BIOMARKERS.items() if b["kind"] == "numeric"]
TEXT = [name for name, b in BIOMARKERS.items() if b["kind"] == "text"]


@pytest.mark.parametrize("name", NUMERIC)
def test_conversions_use_normalized_units_and_include_canonical(name):
    biomarker = BIOMARKERS[name]
    for unit in biomarker["conversions"]:
        assert normalize_unit(unit) == unit, f"{name}: conversion unit {unit!r} isn't normalized"
    assert biomarker["conversions"].get(biomarker["unit"]) == 1, f"{name}: canonical unit must convert with factor 1"


@pytest.mark.parametrize("name", NUMERIC)
def test_plausible_range_is_ordered(name):
    low, high = BIOMARKERS[name]["plausible"]
    assert low < high


@pytest.mark.parametrize("panel_id", PANELS)
def test_panel_members_are_known_biomarkers(panel_id):
    panel = PANELS[panel_id]
    for member in panel["required"] + panel["optional"]:
        for name in member if isinstance(member, tuple) else (member,):
            assert name in BIOMARKERS, f"{panel_id}: unknown biomarker {name!r}"


@pytest.mark.parametrize("name", TEXT)
def test_text_biomarkers_have_answers_and_no_units(name):
    biomarker = BIOMARKERS[name]
    assert biomarker["answers"], f"{name}: a text biomarker needs answers"
    assert biomarker["unit"] is None and not biomarker["conversions"] and biomarker["plausible"] is None


@pytest.mark.parametrize("name", [n for n, b in BIOMARKERS.items() if b["answers"]])
def test_answers_are_normalized_and_have_known_statuses(name):
    for answer, status in BIOMARKERS[name]["answers"].items():
        assert normalize_answer(answer) == answer, f"{name}: answer {answer!r} isn't normalized"
        assert status in ("normal", "abnormal", None)


@pytest.mark.parametrize("text, normalized", [
    ('"A"', "a"), ("Present (+)", "present"), ("Non-Reactive", "non reactive"), ("+ve", "+ve"), ("-VE", "-ve"), ("B Positive", "b positive"),
])
def test_normalize_answer(text, normalized):
    assert normalize_answer(text) == normalized


@pytest.mark.parametrize("panel_id", PANELS)
def test_panel_inputs_are_its_tests_without_duplicates(panel_id):
    panel = PANELS[panel_id]
    members = {n for m in panel["required"] + panel["optional"] for n in (m if isinstance(m, tuple) else (m,))}
    assert len(panel["inputs"]) == len(set(panel["inputs"]))
    assert set(panel["inputs"]) == members
    assert isinstance(panel["schema_version"], int) and 0 < panel["min_coverage"] <= 1
