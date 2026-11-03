You are writing a forecasting formula, to be frozen before it ever sees a test case. Work only inside
/home/claude/ideas/overnight/reading/rung3_train/ (read-only) and write your output to
/home/claude/ideas/overnight/reading/rung3/. Do not open any other directory (in particular not `packets/`,
`predictions/`, `private/`, any git repository or results directory), and do not search the web.

The training set holds historical routed runs of TRAINING designs only (sky130A, LibreLane 3.0.16), each in packet
format E1.0 (see README.md there): `runs/<run_id>/` with `contract.json`, `reports/summary.txt`, `metrics.json`,
`reports/checks/*.rpt`, `nets/drv.json`, and for most runs `nets/postgrt.jsonl.gz` (per-net dump after global route),
`nets/connectivity.json.gz`, and for small designs `nets/signoff.jsonl.gz`. `labels.csv` gives, per run, the observed
response of the same settings at another clock (partner run: exactly at R1 = ceil05(C0) when `partner_is_R1` = 1,
else the nearest target), its pass/fail under the judge, the slope (C_partner − C0)/(T_partner − T0), chain outcomes
where a registered-style chain was run, and the setting's smallest passing target (F_obs) and interpolated fixed
point (F_emp). `pairs.csv` gives every pair of runs of the same setting. `family` is a pseudonymous design family:
validate across families (leave-one-family-out), because the test designs are different families.

Task: write `/home/claude/ideas/overnight/reading/rung3/formula.py` defining `predict(run_dir: str) -> dict` that,
for ONE run directory in this format (test directories also contain `layout/` and `sta/`, which you must not
require), returns {"p_pass": float 0..1, "call": "pass"|"fail"|"abstain", "slope": float,
"kept_clock_ns": float or None} for the registered chain described in `contract.json` (first rebuild at
`chain.R1_ns`, slope = (C1 − C0)/(R1 − T0), kept clock as defined there). Rules: a written formula over raw fields
(you may fit its constants on the training set and hard-code them); deterministic; Python standard library (+ numpy
if available); it may read only files inside `run_dir`; it must work when `nets/signoff.jsonl.gz` or
`nets/postgrt.jsonl.gz` is absent. Also write `rung3/NOTES.md` (≤ 300 words: the formula, the fields it uses, and its
leave-one-family-out slope error on the training set). The file's SHA-256 will be committed before it is run on any
test packet; you will not see the test results.
