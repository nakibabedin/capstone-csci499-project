"""Check the panels detected in a report against an answer key's `expected_panels`.

    python score_panels.py /path/to/report.pdf expected/sterling-accuris-sample.json

Exits non-zero if any panel is missing, unexpected, or has the wrong status or missing tests.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from lab_parser import parse_lab_report  # noqa: E402

MAX_PAGES = 20


def main(pdf_path, expected_path):
    expected = json.loads(Path(expected_path).read_text())["expected_panels"]
    report, _ = parse_lab_report(Path(pdf_path).read_bytes(), MAX_PAGES)
    detected = {p["id"]: p for p in (report or {}).get("panels", [])}

    problems = []
    for panel_id, want in expected.items():
        got = detected.get(panel_id)
        if got is None:
            problems.append(f"{panel_id}: not detected")
        elif got["status"] != want["status"] or got["missing"] != want["missing"]:
            problems.append(f"{panel_id}: got {got['status']} missing {got['missing']}, "
                            f"expected {want['status']} missing {want['missing']}")
    problems += [f"{panel_id}: detected but not expected" for panel_id in detected.keys() - expected.keys()]

    wrong = {p.split(":")[0] for p in problems} & expected.keys()
    print(f"{len(expected) - len(wrong)}/{len(expected)} expected panels correct")
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:]))
