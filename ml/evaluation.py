"""Shared data preparation and survey-weighted metrics for the liver model notebooks.

Every metric takes NHANES exam weights (`weight`), so results describe the US adult
population rather than the sample.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

# Elastography CAP at or above this is labelled fatty liver (a common NHANES cut-off).
CAP_CUTOFF = 285


def prepare_liver(adults):
    """Adults with a complete elastography exam, with the `fatty_liver` label and a 0/1 `male`."""
    data = adults[adults["elastography_complete"] & adults["cap_dbm"].notna()].copy()
    data["fatty_liver"] = (data["cap_dbm"] >= CAP_CUTOFF).astype(int)
    data["male"] = (data["sex"] == "male").astype(int)
    return data


def hide(frame, columns, rate, seed):
    """Randomly blank `rate` of the values in `columns`, like reports or users that skip them."""
    out = frame.copy()
    mask = np.random.default_rng(seed).random((len(out), len(columns))) < rate
    out[columns] = out[columns].mask(mask)
    return out


def weighted_auc(d, scores):
    return roc_auc_score(d["fatty_liver"], scores, sample_weight=d["weight"])


def bootstrap_ci(d, statistic, n=400, seed=0):
    """95% bootstrap interval of statistic(sample) over row resamples of d."""
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(n):
        sample = d.iloc[rng.integers(0, len(d), len(d))]
        if sample["fatty_liver"].nunique() == 2:
            stats.append(statistic(sample))
    return np.percentile(stats, [2.5, 97.5])


def calibration_summary(d, p):
    """Mean predicted vs observed, calibration slope, expected calibration error (10 risk
    deciles), Brier score, and the per-decile table."""
    y, w = d["fatty_liver"].to_numpy(), d["weight"].to_numpy()
    frame = pd.DataFrame({"y": y, "p": p, "w": w, "bin": pd.qcut(p, 10, labels=False, duplicates="drop")})
    per_bin = frame.groupby("bin").apply(lambda g: pd.Series({
        "predicted": np.average(g["p"], weights=g["w"]), "observed": np.average(g["y"], weights=g["w"]), "w": g["w"].sum()}))
    ece = np.average((per_bin["predicted"] - per_bin["observed"]).abs(), weights=per_bin["w"])
    clipped = np.clip(p, 1e-6, 1 - 1e-6)
    logit = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    slope = LogisticRegression(C=np.inf).fit(logit, y, sample_weight=w).coef_[0][0]  # unpenalized
    return {"mean predicted": np.average(p, weights=w), "observed": np.average(y, weights=w),
            "calibration slope": slope, "expected calibration error": ece,
            "Brier": brier_score_loss(y, p, sample_weight=w)}, per_bin


def weighted_rates(d, p, threshold):
    """Share flagged, sensitivity, specificity, PPV and NPV when flagging p >= threshold."""
    y, w, flag = d["fatty_liver"].to_numpy(), d["weight"].to_numpy(), np.asarray(p) >= threshold
    tp, fp = w[flag & (y == 1)].sum(), w[flag & (y == 0)].sum()
    fn, tn = w[~flag & (y == 1)].sum(), w[~flag & (y == 0)].sum()
    return {"threshold": threshold, "flagged": (tp + fp) / w.sum(), "sensitivity": tp / (tp + fn),
            "specificity": tn / (tn + fp), "PPV": tp / (tp + fp) if tp + fp else np.nan,
            "NPV": tn / (tn + fn) if tn + fn else np.nan}


def threshold_for(d, p, sensitivity=None, specificity=None):
    """The highest threshold reaching `sensitivity`, or the lowest reaching `specificity`."""
    rates = [weighted_rates(d, p, t) for t in np.unique(np.round(p, 4))]
    if sensitivity is not None:
        return max(r["threshold"] for r in rates if r["sensitivity"] >= sensitivity)
    return min(r["threshold"] for r in rates if r["specificity"] >= specificity)


def subgroups(d, p, min_size=150, n_boot=200):
    """AUROC (with CI), observed and mean predicted risk by sex, race/ethnicity and age band."""
    d = d.assign(p=p, age_band=pd.cut(d["age"], [18, 40, 60, 81], right=False, labels=["18–39", "40–59", "60–80"]))
    rows = []
    for column in ["sex", "race_ethnicity", "age_band"]:
        for value, g in d.groupby(column, observed=True):
            if g["fatty_liver"].nunique() < 2 or len(g) < min_size:
                continue
            low, high = bootstrap_ci(g, lambda s: weighted_auc(s, s["p"]), n=n_boot)
            rows.append({"group": f"{column}: {value}", "adults": len(g),
                         "fatty liver": np.average(g["fatty_liver"], weights=g["weight"]),
                         "mean predicted": np.average(g["p"], weights=g["weight"]),
                         "AUROC": weighted_auc(g, g["p"]), "95% CI": f"{low:.3f}–{high:.3f}"})
    return pd.DataFrame(rows).set_index("group")
