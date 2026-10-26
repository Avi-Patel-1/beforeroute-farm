# Repair-policy candidates — proposal log

Kept in the spirit of Meta-Harness (Lee et al., 2026): every candidate policy is recorded with
its scores *and* a pointer to its raw traces (`results/<base>-<arm>/`: `repair_step.log` or the
targeted step log, `targeted_summary.json`, `labels.json` per net, `checks/*.checks.rpt`,
`metrics.json`). The next proposal is made after reading those traces, never from the score
alone, and is evaluated on bases the model never saw.

A policy = (model, k = fraction of signal nets flagged, H = slew/cap margin %, tiers).
Scores: V = signal nets violating at nine-corner signoff (baseline in brackets), E = cells changed
by the repair step (resized + buffers; all four targeted arms were re-run locally to recover
their logs and reproduced the farm metrics bit-for-bit), hold = hold worst slack in ns (baseline in brackets), ΔA = std-cell area vs baseline.

## Round 0 — exploratory, base `picorv32-base-v1` (model v1: 3 runs, no PicoRV32)

| arm | V (352) | E | hold (0.106) | ΔA | trace |
|---|---|---|---|---|---|
| uni10 | 338 | 117 | 0.106 | −0.54% | results/picorv32-base-v1-uni10 |
| uni30 | 324 | 507 | 0.106 | −2.32% | …-uni30 |
| uni50 | 152 | 750 | 0.097 | −2.94% | …-uni50 |
| uni70 | 4 | 1,248 | 0.025 | −2.35% | …-uni70 |
| tgt020-70 | 163 | 198 | 0.091 | −0.53% | …-tgt020-70 (+ -L re-run) |
| **tgt050-70** | 7 | 469 (453 resized + 16 buffers) | 0.094 | −1.19% | …-tgt050-70 (+ -L re-run) |
| tgt050-90 | 5 | 789 (482 + 307 buffers) | 0.037 | +4.48% | …-tgt050-90 (+ -L re-run) |
| tgt100-70 | 5 | 618 | 0.028 | −1.39% | …-tgt100-70 (+ -L re-run) |

What the traces said:
* `uni70/repair_step.log`: RSZ found 1,402 slew violations at a 70% margin and touched 1,197
  nets; `metrics.json` shows the timing-repair-buffer area dropping from 27,172 to 23,795 µm² —
  the resizer swaps hold-fix delay cells for faster buffers, which is where the hold margin goes
  (0.106 → 0.025 ns). The "area saving" of uniform repair is a hold-margin spend.
* `tgt050-70/targeted_summary.json`: 483 nets eligible, 9,395 masked, 16 buffers inserted; the
  7 residual violators in `labels.json` are 4 fanout-rule nets (fanout 11–12) and 3 slews at
  1.01–1.07× the limit in a single corner. The 4 fanout nets were *slew* violators with fanout
  exactly 10 in the baseline (`net1230/1215/1235/1236`, delay-cell drivers, all flagged, slew
  fixed by the arm). Pin diff of `final_nets.json` (local re-run, 16:40): the extra 1–2 loads are
  `ANTENNA_*/DIODE` pins — antenna diodes that the flow's post-route antenna repair attached to
  these nets, which the signoff fanout check then counts. Not a repair artifact and not a slew
  problem; the deck reports fanout residuals separately and says what they are.
* Score ranks 484–966 (the extra nets tgt100-70 makes eligible) contain only 2 violators
  (92 of the 483 are delay-cell nets, the rest ordinary logic), yet tgt100-70 ends at hold
  0.028 ns: those nets buy 2 violators and cost most of the hold margin. tgt050-90 keeps the
  same 483 nets but the 90% margin upsizes harder: +4.5% area, hold 0.037 ns.

Decision (16:00 EDT, before any confirmatory result): k = 5%, H = 70% is the operating point.
Next proposals: (a) a two-tier policy, top 2% at 80% margin, next 3% at 50%, to see whether a
softer margin on the lower-confidence tier keeps the hold margin without losing violators
(in Round 1); (b) a rule that makes any net already over MAX_FANOUT at post-GRT eligible
regardless of score (no such net exists in `picorv32-base-v1`, so this is only a safety net).
A two-pass option was implemented while the fanout residuals were still suspected to be
repair-created; the pin diff above removed that motivation, so it is not in Round 2.

## Round 1 — confirmatory (dispatched 19:45 UTC)

Bases: `d1-aes_cipher-000` (model `model_holdout_aes_v2`, 24 runs without AES),
`d1-picorv32-016`, `d1-picorv32-006` (model `model_holdout_picorv32_v2`, 24 runs without
PicoRV32). Arms: rerun, uni30, uni50, uni70, tgt030-70, tgt050-70, tgt050-80,
tier020-80_050-50. Results are appended below as they land, with no post-hoc arm selection.

### Results so far (17:10 EDT) — v2 held-out models, pre-registered k = 5%, H = 70%

`d1-aes_cipher-000` (baseline 830 violating signal nets = 7.4% of nets; hold 0.114 ns):

| arm | V (830) | E cells | nets touched | hold | ΔA |
|---|---|---|---|---|---|
| uni30 | 538 | 842 | 863 | 0.114 | −2.87% |
| uni50 | 228 | 1,302 | 1,325 | 0.035 | −2.58% |
| uni70 | 10 | 3,957 | 3,634 | 0.026 | **+10.0%** |
| tgt030-70 | 478 | 367 | 311 | 0.107 | −0.47% |
| **tgt050-70** | 257 | 665 | 530 | 0.103 | −0.23% |
| tgt050-80 | 269 | 737 | 564 | 0.089 | +1.15% |
| tier020-80_050-50 | 304 | 559 | 370 | 0.104 | −0.46% |

`d1-picorv32-016` (baseline 515 = 5.0% of nets; hold 0.107 ns; uni70 still running):

| arm | V (515) | E cells | nets touched | hold | ΔA |
|---|---|---|---|---|---|
| uni30 | 429 | 426 | 431 | 0.100 | −1.63% |
| uni50 | 232 | 777 | 736 | 0.033 | −1.82% |
| tgt030-70 | 201 | 368 | 284 | 0.097 | −0.29% |
| **tgt050-70** | 68 | 576 | 483 | 0.070 | −0.37% |
| tgt050-80 | 75 | 651 | 510 | 0.036 | +1.10% |
| tier020-80_050-50 | 145 | 428 | 315 | 0.028 | −0.21% |

What the traces say:
* PicoRV32-016 meets the pre-registered criterion: tgt050-70 removes 87% of violators with
  fewer cells than uni50 (576 vs 777), 3.4× fewer violators left, and 65% of the hold margin
  kept (uni50: 31%).
* AES does **not** meet it at k = 5%: 69% removed. Cause, from the flagged list: the top 5% is
  564 nets and 563 of them are true violators (precision 99.8%, lowest flagged p = 0.996) — the
  budget was smaller than the violator population (830 = 7.4% of nets). Rescoring the same run:
  a probability threshold p ≥ 0.5 flags 7.6% of nets with recall 94.6% / precision 91%
  (`score.py --threshold 0.5`, v2 and v3 models agree). A fixed fraction was the wrong knob;
  the classifier's own threshold is the natural budget.
* The tiered arm (top 2% at 80%) costs hold margin on PicoRV32-016 (0.028) — the 80% margin
  upsizes the delay cells hardest. Margin above 70% is not free.
* Hold-margin loss tracks how aggressively the hold-fix delay cells get resized, in every arm.

Round 2 (dispatched 17:12 EDT, v3 held-out models, same three bases): `thr500-70v3`
(threshold budget), `tgt050-70v3` (model-version control), `tgt050-70hv3` and `thr500-70hv3`
(hold-fix delay cells marked do-not-touch at the instance level, so their nets can be buffered
but the cells are not swapped), `lt050-80-60-40` (learned margins by predicted ratio).

## Model update (16:30 EDT) — v3, 61 runs / 395,737 nets, leave-one-design-out

| held out | runs | violators | PR-AUC | nets flagged to catch 95% (model) | same, timer estimate |
|---|---|---|---|---|---|
| PicoRV32 | 34 | 13,292 | 0.969 | 4.5% | 44.0% |
| AES | 4 | 2,740 | 0.980 | 6.6% | 9.4% |
| CRC | 20 | 68 | 0.842 | 0.7% | 97.8% |

The regression variant (predict log signoff ratio) now transfers: log-MAE 0.05–0.09 vs 0.08–0.22
for the estimate, and 78–100% of true violators are predicted over the limit (estimate: 9–18%).
Trace: `results/model_v3/report.json`, `models/report_v3.json`.

## Round 2 — proposals (to run on the Round-1 bases once Round 1 has landed; v3 held-out models)

| arm | what changes | why (from the traces) |
|---|---|---|
| `lt050-80-60-40` | top 5% split by predicted signoff ratio ≥1.3 / ≥1.1 / rest at margins 80 / 60 / 40 | regression is now calibrated; spend margin where the predicted overshoot is large, keep hold margin elsewhere |
| `tgt050-70v3` | same policy, v3 model (61 runs) instead of v2 (24 runs) | isolates the effect of more training runs on the intervention |

