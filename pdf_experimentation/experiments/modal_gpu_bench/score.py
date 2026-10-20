"""Score extracted lab results against a hand-verified answer key.

Predictions are dicts with `test`, `value`, `unit`, `reference_range`, `flag` and,
when known, `page`. The rule parser's output is adapted with `from_rule_parser`.

    python score.py ../../eval/expected/sterling-accuris-sample.json predictions.json
"""

import json
import re
import sys

# Words shared by many unrelated tests; they can't make two names "the same test".
GENERIC_WORDS = {
    "count", "total", "serum", "blood", "plasma", "level", "test", "ratio", "cells", "type",
    "peak", "interpretation", "of", "and", "the", "with", "per", "in",
}
FLAG_WORDS = {"h": "H", "high": "H", "hh": "H", "l": "L", "low": "L", "ll": "L"}


def _words(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower())) - GENERIC_WORDS


def _nums(text):
    return sorted(float(x) for x in re.findall(r"\d+(?:\.\d+)?", (text or "").replace(",", "")))


def _value_key(value):
    """Comparable form of a value: '< 148' -> '<148.0', '02' -> '2.0', 'Present (+)' -> 'present (+)'."""
    text = re.sub(r"\s+", " ", str(value or "")).strip().strip('"').lower()
    m = re.fullmatch(r"([<>]=?)?\s*(\d[\d,]*(?:\.\d+)?)", text)
    if m:
        return (m.group(1) or "") + str(float(m.group(2).replace(",", "")))
    return text


def _unit_key(unit):
    return re.sub(r"\s+", "", (unit or "").lower())


def _flag_key(flag):
    return FLAG_WORDS.get((flag or "").strip().lower(), (flag or "").strip().upper())


def from_rule_parser(results):
    return [
        {"test": r["test"], "value": r["value_text"], "unit": r["unit"] or "",
         "reference_range": r["reference_range"] or "", "flag": r["flag"] or "", "page": r["page"]}
        for r in results
    ]


def _same_page(pred, want):
    return pred.get("page") is None or pred["page"] == want["page"]


def score(expected, predictions):
    """Match predictions to answer-key rows and classify every miss."""
    rows = expected["results"]
    excluded = {int(p) for p in expected.get("excluded_pages", {})}
    unused = list(predictions)
    matched = []
    for want in rows:
        candidates = [
            p for p in unused
            if _same_page(p, want)
            and _value_key(p["value"]) == _value_key(want["value"])
            and _words(p["test"]) & _words(want["test"])
        ]
        if candidates:
            best = max(candidates, key=lambda p: len(_words(p["test"]) & _words(want["test"])))
            unused.remove(best)
            matched.append((want, best))

    matched_rows = {id(w) for w, _ in matched}
    missed = [w for w in rows if id(w) not in matched_rows]

    # Leftover predictions: wrong-row values (named like a real row on that page but
    # carrying a number from its range or from another row), excluded-page
    # duplicates, and anything else.
    wrong_row, from_excluded, other = [], [], []
    for p in unused:
        if p.get("page") in excluded:
            from_excluded.append(p)
            continue
        same_page = [w for w in rows if _same_page(p, w)]
        named = max(same_page, key=lambda w: len(_words(p["test"]) & _words(w["test"])), default=None)
        if named and _words(p["test"]) & _words(named["test"]):
            value = _value_key(p["value"])
            if value in {_value_key(n) for n in _nums(named["reference_range"])} or value in {
                _value_key(w["value"]) for w in same_page if w is not named
            }:
                wrong_row.append({**p, "expected_value": named["value"]})
                continue
        other.append(p)

    def accuracy(field_key, field):
        return sum(field_key(w[field]) == field_key(p.get(field)) for w, p in matched)

    by_type = {}
    for w in rows:
        hit = id(w) in matched_rows
        found, total = by_type.get(w["value_type"], (0, 0))
        by_type[w["value_type"]] = (found + hit, total + 1)

    return {
        "expected": len(rows),
        "predicted": len(predictions),
        "matched": len(matched),
        "recall": len(matched) / max(1, len(rows)),
        "precision": len(matched) / max(1, len(predictions)),
        "recall_by_type": {t: f"{f}/{n}" for t, (f, n) in by_type.items()},
        "unit_correct": accuracy(_unit_key, "unit"),
        "range_correct": sum(_nums(w["reference_range"]) == _nums(p.get("reference_range")) for w, p in matched),
        "flag_correct": accuracy(_flag_key, "flag"),
        "wrong_row": wrong_row,
        "from_excluded_pages": from_excluded,
        "other_unmatched": other,
        "missed": missed,
    }


def print_score(label, s):
    m = max(1, s["matched"])
    print(f"\n### {label}")
    print(f"  matched {s['matched']}/{s['expected']} (recall {s['recall']:.0%}, precision {s['precision']:.0%}); "
          f"by type {s['recall_by_type']}")
    print(f"  of matched: unit {s['unit_correct']}/{m}, range {s['range_correct']}/{m}, flag {s['flag_correct']}/{m}")
    print(f"  WRONG-ROW values: {len(s['wrong_row'])} "
          f"{[(p['test'], p['value'], 'expected ' + p['expected_value']) for p in s['wrong_row']]}")
    print(f"  from excluded pages: {len(s['from_excluded_pages'])}; "
          f"other unmatched: {[(p['test'], p['value']) for p in s['other_unmatched']]}")
    missed = [(w["page"], w["test"], w["value"]) for w in s["missed"]]
    print(f"  missed ({len(missed)}): {missed[:25]}{' ...' if len(missed) > 25 else ''}")


if __name__ == "__main__":
    expected = json.load(open(sys.argv[1]))
    predictions = json.load(open(sys.argv[2]))["results"]
    print_score(sys.argv[2], score(expected, predictions))
