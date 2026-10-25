"""Whether a result is normal, from the report's own flags, ranges and answers.

Mirrored by resultStatus() in frontend/src/components/status.tsx; keep them in sync.
"""


def result_status(result):
    """HIGH / LOW / ABNORMAL from the report's flag, else from the reference range
    or, for a word answer, from what the answer means (see `text_status` in panels.enrich).

    "unknown" when there is none of these, so a result is never called normal
    without something to back it up.
    """
    flag = result.get("flag")
    if flag in ("H", "HH"):
        return "HIGH"
    if flag in ("L", "LL"):
        return "LOW"
    if flag:
        return "ABNORMAL"
    if result.get("value") is None and result.get("text_status"):
        return "normal" if result["text_status"] == "normal" else "ABNORMAL"
    # A value like ">60" can't be compared precisely, so trust the (absent) flag.
    if (result.get("value_text") or "")[:1] in "<>":
        return "normal"
    value, low, high = result.get("value"), result.get("ref_low"), result.get("ref_high")
    if value is None or (low is None and high is None):
        return "unknown"
    if high is not None and value > high:
        return "HIGH"
    if low is not None and value < low:
        return "LOW"
    return "normal"
