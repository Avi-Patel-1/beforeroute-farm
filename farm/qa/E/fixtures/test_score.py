#!/usr/bin/env python3
"""Scorer fixture (Addendum 42 clarification 2): landed pass, landed fail, first rebuild without metrics (undefined
slope), chain record never landed (not checked), source-only kept clock, null kept clock, an invalid prediction file.
Run: python3 farm/qa/E/fixtures/test_score.py  -> prints OK or raises AssertionError."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCORE = os.path.join(HERE, "..", "score.py")
CH = {  # pid: chain record (None = never landed)
    "RA": {"T0_ns": 10.0, "C0_ns": 9.0, "first_pass": True, "first_outcome": "landed", "C1_ns": 9.3, "slope": 0.3, "kept_clock_ns": 8.5},
    "RB": {"T0_ns": 10.0, "C0_ns": 11.0, "first_pass": False, "first_outcome": "landed", "C1_ns": 11.6, "slope": 0.6, "kept_clock_ns": None},
    "RC": {"T0_ns": 10.0, "C0_ns": 11.0, "first_pass": False, "first_outcome": "no_metrics", "C1_ns": None, "slope": None, "kept_clock_ns": None},
    "RD": None,
    "RE": {"T0_ns": 10.0, "C0_ns": 8.0, "first_pass": False, "first_outcome": "landed", "C1_ns": 10.5, "slope": -1.25, "kept_clock_ns": 10.0},
    "RF": {"T0_ns": 10.0, "C0_ns": 9.5, "first_pass": True, "first_outcome": "landed", "C1_ns": 9.4, "slope": 0.2, "kept_clock_ns": 9.5},
}
PRED = {
    "RA": {"p_pass": 0.9, "call": "pass", "slope": 0.4, "kept_clock_ns": 8.6},
    "RB": {"p_pass": 0.2, "call": "fail", "slope": 0.5, "kept_clock_ns": None},
    "RC": {"p_pass": 0.6, "call": "pass", "slope": 0.7, "kept_clock_ns": 11.2},
    "RD": {"p_pass": 0.5, "call": "pass", "slope": 0.1, "kept_clock_ns": 9.0},
    "RE": {"p_pass": 0.5, "call": "pass", "slope": 0.1},            # invalid: no kept_clock_ns key
    "RF": {"p_pass": 0.7, "call": "abstain", "slope": 0.3, "kept_clock_ns": None},
}


def main():
    d = tempfile.mkdtemp(prefix="e_score_fixture_")
    key = {"packets": {}}
    chains = []
    for i, (pid, c) in enumerate(CH.items()):
        src = f"ers-fam{i % 2}-{i:02d}"
        key["packets"][pid] = {"source": src, "design": f"fam{i % 2}", "kind": "main", "has_second_point": False}
        tag = src.replace("ers-", "erk-")
        chains.append({"source": src, "tag": tag})
        if c is not None:
            os.makedirs(os.path.join(d, "chains", tag))
            json.dump(c, open(os.path.join(d, "chains", tag, "chain.json"), "w"))
        os.makedirs(os.path.join(d, "pred", "rung1"), exist_ok=True)
        json.dump(dict(PRED[pid], packet_id=pid, arm="rung1"), open(os.path.join(d, "pred", "rung1", pid + ".json"), "w"))
    json.dump(key, open(os.path.join(d, "key.json"), "w"))
    json.dump({"chains": chains}, open(os.path.join(d, "chains.json"), "w"))
    out = os.path.join(d, "score.json")
    subprocess.run([sys.executable, SCORE, "--chains", os.path.join(d, "chains"), "--key", os.path.join(d, "key.json"),
                    "--pred", os.path.join(d, "pred"), "--out", out, "--chains-index", os.path.join(d, "chains.json")],
                   check=True, capture_output=True)
    r = json.load(open(out))
    a = r["arms"]["rung1"]
    assert r["n_checked"] == 5 and r["not_checked"] == ["RD"], r
    assert r["first_rebuild_no_metrics"] == ["RC"] and r["slope_undefined"] == ["RC"], r
    assert r["kept_null"] == ["RB", "RC"] and r["kept_source_only"] == ["RE"], r
    assert (a["n"], a["predicted_passes"], a["false_passes"], a["actual_passes"], a["missed_passes"],
            a["abstentions"], a["correct"]) == (5, 2, 1, 2, 0, 2, 2), a
    assert abs(a["brier"] - 0.15) < 1e-12, a["brier"]
    assert a["slope_defined"] == 4 and a["slope_missing"] == 1, a
    assert abs(a["slope_err_median"] - 0.1) < 1e-9 and abs(a["slope_err_mean"] - 0.1) < 1e-9, a
    assert a["kept_missing"] == 1 and a["kept_n"] == 2 and a["kept_vs_none_agree"] == 2, a
    assert abs(a["kept_err_median"] - (0.1 / 8.5 + 1.0) / 2) < 1e-9 and a["kept_err_p90"] == 1.0, a
    print("OK score fixture:", d)


if __name__ == "__main__":
    main()
