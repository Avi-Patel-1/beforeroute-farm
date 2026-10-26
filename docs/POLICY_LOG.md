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

### Round 1 complete + Round 2 (18:30 EDT)

`d1-picorv32-006` (baseline 438 = 4.6% of nets; hold 0.109 ns), v2 model:

| arm | V (438) | E cells | hold | ΔA |
|---|---|---|---|---|
| uni30 | 421 | 566 | 0.110 | −2.47% |
| uni50 | 173 | 816 | 0.108 | −3.21% |
| uni70 | 11 | 1,351 | 0.024 | −2.35% |
| tgt030-70 | 161 | 302 | 0.110 | −0.78% |
| **tgt050-70** | **39** | **502** | **0.110** | −1.10% |
| tgt050-80 | 44 | 489 | 0.109 | −0.43% |
| tier020-80_050-50 | 139 | 432 | 0.111 | −1.17% |

`d1-picorv32-016` uni70 landed: 12 left, 2,791 cells, hold 0.033 (31%), area +2.6%.

Pre-registered test, k = 5% / H = 70%, three held-out bases: PicoRV32-016 removes 87%,
PicoRV32-006 removes 91%, AES removes 69% (budget-limited, see above). In all three the
targeted arm changes 35–50% as many cells as uni70 and keeps 65–100% of the hold margin
(uni70: 22–31%).

Round 2 arms (v3 held-out models):

| base | arm | V | E cells | hold kept | note |
|---|---|---|---|---|---|
| AES | tgt050-70v3 | 254 | 655 | 90% | ≈ v2 (257): model version barely matters |
| AES | lt050-80-60-40 | 293 | 622 | 91% | worse than one 70% margin |
| AES | tgt050-70hv3 | 809 | – | 100% | hold-cell protection disables the repair |
| PicoRV32-016 | tgt050-70v3 | 65 | 571 | 61% | ≈ v2 (68) |
| PicoRV32-016 | thr500-70v3 | 90 | 506 | 88% | p ≥ 0.5 → 438 eligible instead of 510; cheaper, slightly more residual |
| PicoRV32-016 | lt050-80-60-40 | 159 | 430 | 34% | worse on both axes |
| PicoRV32-016 | tgt050-70hv3 / thr500-70hv3 | 505 | – | 99% | repair disabled |
| PicoRV32-006 | lt050-80-60-40 | 110 | 459 | 100% | worse than tgt050-70 (39) |

What the traces say:
* **Hold-cell protection is a negative result that explains the mechanism.** With the hold-fix
  delay cells marked do-not-touch (1,723 on AES, 2,194 on PicoRV32-016) the masked
  `repair_design` fixes essentially nothing: the signoff violators *are* nets driven by those
  delay cells, and the resizer's fix is to swap the delay cell for a faster buffer. Hold margin
  is therefore the intrinsic price of fixing these nets; targeted repair keeps the price low by
  paying it on 5% of nets instead of all of them.
* **Learned-margin tiers (80/60/40 by predicted ratio) lose to a single 70% margin** on all
  three bases: the 40–60% tiers leave their nets unfixed and the 80% tier spends hold margin.
  Dropped. (The regression is still useful as an estimate; it is not a better margin schedule.)
* **v3 vs v2 model: no material difference** in the intervention (254 vs 257, 65 vs 68). The
  ranking at the top is already right with 24 runs; more data sharpens recall curves, not arms.
* **Threshold budget** (p ≥ 0.5) behaves as intended on PicoRV32-016 (fewer eligible, cheaper,
  hold kept). The AES threshold arm is the decisive one and is still running.

New-design baselines (d3): bm64 275, des 321, md5 192, ocs_blitter 392, salsa20 1,259, y_huff
462 violating nets — six new held-out families for the model. sha512 and ldpcenc (and one
salsa20 config) crash in OpenROAD's antenna repair (GRT-0183 heap underflow, unrelated to this
work); re-dispatched with `RUN_ANTENNA_REPAIR: false` as d3b/d4b, to be reported as such.

### Round 2 complete (19:30 EDT)

| base | arm | V | E cells | hold kept | ΔA |
|---|---|---|---|---|---|
| AES | thr500-70v3 (p ≥ 0.5 → 885 eligible = 7.8%) | **54** (93.5% removed) | 1,072 | 26% | +0.75% |
| AES | thr500-70hv3 | 798 | – | 99% | repair disabled |
| PicoRV32-006 | tgt050-70v3 | 29 | 507 | 101% | −1.21% |
| PicoRV32-006 | thr500-70v3 (416 eligible = 4.3%) | 63 | 448 | 100% | −1.03% |
| PicoRV32-006 | tgt050-70hv3 / thr500-70hv3 | 381 / 386 | – | 101% | repair disabled |

* The threshold budget does what it was proposed for on AES: 93.5% of violators removed with
  1,072 cells (uni50: 73% with 1,302; uni70: 99% with 3,957 and +10% area). Its price is the
  hold margin (26% kept, like uni50): the extra 321 eligible nets include the hold-critical
  delay cells. So on AES the policy offers two honest operating points — k = 5%: 69% removed,
  90% hold margin kept; p ≥ 0.5: 93.5% removed, 26% kept — and both dominate the uniform arms
  on edits. On PicoRV32-006 the threshold undershoots (416 < 477 eligible) and leaves 63 vs 29.
* Hold-cell protection: negative on all three bases (confirms the mechanism).

## Model v4 — 111 runs, 597,620 nets, 10 designs, leave-one-design-out (19:30 EDT)

| held-out design | runs | violators | PR-AUC | recall at 5% flagged | nets to catch 95% | estimate: recall at 5% | estimate: nets to catch 95% |
|---|---|---|---|---|---|---|---|
| BM64 | 1 | 275 | 0.957 | 100.0% | 2.8% | 86.5% | 96.6% |
| aes_cipher_top | 12 | 8,562 | 0.979 | 77.1% | 6.8% | 70.6% | 10.0% |
| crc_pipe | 31 | 95 | 0.850 | 100.0% | 0.6% | 53.7% | 99.1% |
| des | 1 | 321 | 0.962 | 100.0% | 2.5% | 72.6% | 66.5% |
| md5 | 1 | 192 | 0.989 | 99.5% | 2.9% | 92.7% | 44.3% |
| ocs_blitter | 1 | 392 | 0.992 | 93.1% | 5.1% | 82.4% | 6.7% |
| picorv32 | 35 | 13,730 | 0.977 | 97.6% | 4.3% | 84.9% | 44.9% |
| salsa20 | 1 | 1,259 | 0.984 | 95.6% | 4.9% | 84.4% | 7.1% |
| y_huff | 1 | 462 | 0.976 | 100.0% | 3.0% | 92.4% | 8.7% |

Every held-out design comes from a different family (RISC-V core, AES, DES, SHA/MD5, salsa20,
Huffman, LDPC-style, blitter, CRC, SPM). Flagging 5% of nets catches 93–100% of signoff
violators on 8 of 9 held-out designs with violators; AES is 77% because 6.4% of its nets
violate. Trace: `models/report_v4_111runs.json`.

Failures in d4/d4b: GRT-0116 congestion at util 40–45 for ldpcenc, salsa20, y_huff (routability
limits of those designs, not tool bugs); sha512/ldpcenc antenna-repair crash fixed by
`RUN_ANTENNA_REPAIR: false` (disclosed).
