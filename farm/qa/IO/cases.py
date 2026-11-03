#!/usr/bin/env python3
"""IO1 case selection (docs/qa_week/IO_PREREG.md, "Cases"). Deterministic; run locally on the landed record.

Population: Addendum 39 (E2)'s 17 rebuilt winners whose first passing rebuild was port-limited (worst setup slack below
the register-to-register worst slack), as docs/qa_week/E2_analysis.py computes them. Winners with identical settings
(same job-spec overrides) are one case (the first by the order below). Per design, sort by sha256 of the winner's
search-run tag and keep the first three; case ids c01.. follow the same sha256 order across designs.
Writes farm/qa/IO/cases.json. Usage: python3 farm/qa/IO/cases.py [--root /home/claude/eda]
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PER_DESIGN = 3
DRV_REF = {"xtea": 0, "usb_cdc_core": 309, "wbqspiflash": 953, "cic_decimator": 89, "zipdiv": 295}  # tune states


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/home/claude/eda")
    a = ap.parse_args()
    sys.argv = [sys.argv[0]]
    src = open(os.path.join(a.root, "docs", "qa_week", "E2_analysis.py")).read().split("if __name__")[0]
    ns = {"__name__": "e2"}
    exec(compile(src, "E2_analysis.py", "exec"), ns)
    rows = [ns["analyse"](w) for w in ns["a32_winners"]() + ns["a35_winners"]()]
    port = [r for r in rows if r["port1"]]
    assert len(port) == 17, len(port)
    seen, uniq, dups = {}, [], []
    for r in sorted(port, key=lambda r: sha(r["best"])):
        spec = json.load(open(os.path.join(REPO, "farm", "jobs", f"{r['best']}.json")))
        key = json.dumps(spec["overrides"], sort_keys=True)
        if key in seen:
            dups.append([seen[key], r["best"]])
            continue
        seen[key] = r["best"]
        uniq.append((r, spec))
    chosen = []
    for d in sorted({r["design"] for r, _ in uniq}):
        chosen += [x for x in uniq if x[0]["design"] == d][:PER_DESIGN]
    chosen.sort(key=lambda x: sha(x[0]["best"]))
    cases = []
    for i, (r, spec) in enumerate(chosen, 1):
        cases.append({
            "case": f"c{i:02d}", "design": r["design"], "design_dir": spec["design"], "config": spec["config"],
            "winner_tag": r["best"], "winner_sha256": sha(r["best"]), "set": r["set"], "arm": r["arm"],
            "seed": r["seed"], "T0": spec["overrides"]["CLOCK_PERIOD"], "claim0_record": r["claim0"],
            "overrides": spec["overrides"], "drv_ref": DRV_REF[r["design"]],
            "record_chain": {"T1_tag": r["T1_tag"], "T1": r["T1"], "kept_tag": r["Tlast_tag"], "kept": r["Tlast"],
                             "gain": r["gain"]}})
    out = {"rule": __doc__.strip().splitlines()[2:6], "population": [r["best"] for r in port],
           "duplicates": dups, "cases": cases}
    json.dump(out, open(os.path.join(HERE, "cases.json"), "w"), indent=1)
    for c in cases:
        print(c["case"], c["design"], c["winner_tag"], "T0", c["T0"], "C0", round(c["claim0_record"], 4),
              "record kept", c["record_chain"]["kept"])


if __name__ == "__main__":
    main()
