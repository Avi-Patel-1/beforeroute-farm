# Repair-policy candidates — proposal log

Kept in the spirit of Meta-Harness (Lee et al., 2026): every candidate policy is recorded with
its scores *and* a pointer to its raw traces (`results/<base>-<arm>/`: `repair_step.log` or the
targeted step log, `targeted_summary.json`, `labels.json` per net, `checks/*.checks.rpt`,
`metrics.json`). The next proposal is made after reading those traces, never from the score
alone, and is evaluated on bases the model never saw.

A policy = (model, k = fraction of signal nets flagged, H = slew/cap margin %, tiers).
Scores: V = signal nets violating at nine-corner signoff (baseline in brackets), E = cells changed
by the repair step (resized + buffers; "+n inst" = std-cell instance delta when the log is
missing), hold = hold worst slack in ns (baseline in brackets), ΔA = std-cell area vs baseline.

## Round 0 — exploratory, base `picorv32-base-v1` (model v1: 3 runs, no PicoRV32)

| arm | V (352) | E | hold (0.106) | ΔA | trace |
|---|---|---|---|---|---|
| uni10 | 338 | 117 | 0.106 | −0.54% | results/picorv32-base-v1-uni10 |
| uni30 | 324 | 507 | 0.106 | −2.32% | …-uni30 |
| uni50 | 152 | 750 | 0.097 | −2.94% | …-uni50 |
| uni70 | 4 | 1,248 | 0.025 | −2.35% | …-uni70 |
| tgt020-70 | 163 | +8 inst | 0.091 | −0.53% | …-tgt020-70 |
| **tgt050-70** | 7 | +19 inst | 0.094 | −1.19% | …-tgt050-70 |
| tgt050-90 | 5 | +299 inst | 0.037 | +4.48% | …-tgt050-90 |
| tgt100-70 | 5 | +43 inst | 0.028 | −1.39% | …-tgt100-70 |

What the traces said:
* `uni70/repair_step.log`: RSZ found 1,402 slew violations at a 70% margin and touched 1,197
  nets; `metrics.json` shows the timing-repair-buffer area dropping from 27,172 to 23,795 µm² —
  the resizer swaps hold-fix delay cells for faster buffers, which is where the hold margin goes
  (0.106 → 0.025 ns). The "area saving" of uniform repair is a hold-margin spend.
* `tgt050-70/targeted_summary.json`: 483 nets eligible, 9,395 masked, 16 buffers inserted; the
  7 residual violators in `labels.json` are 4 fanout-rule nets (fanout 11–12) and 3 slews at
  1.01–1.07× the limit in a single corner. The 4 fanout nets were *slew* violators with fanout
  exactly 10 in the baseline (`net1230/1215/1235/1236`, delay-cell drivers, all flagged): the
  repair pass itself left them with 11–12 loads, i.e. these are repair-created violations that
  a second masked pass would catch (mechanism to be confirmed in the verbose log of the local
  re-run; uni70 leaves 1 such net).
* Score ranks 484–966 (the extra nets tgt100-70 makes eligible) contain only 2 violators
  (92 of the 483 are delay-cell nets, the rest ordinary logic), yet tgt100-70 ends at hold
  0.028 ns: those nets buy 2 violators and cost most of the hold margin. tgt050-90 keeps the
  same 483 nets but the 90% margin upsizes harder: +4.5% area, hold 0.037 ns.

Decision (16:00 EDT, before any confirmatory result): k = 5%, H = 70% is the operating point.
Next proposals: (a) a two-tier policy, top 2% at 80% margin, next 3% at 50%, to see whether a
softer margin on the lower-confidence tier keeps the hold margin without losing violators
(in Round 1); (b) a second masked `repair_design` pass on the same eligible set, so that
violations created by the first pass (the 4 fanout nets above) are cleaned up (Round 2);
(c) a rule that makes any net already over MAX_FANOUT at post-GRT eligible regardless of score
(no such net exists in `picorv32-base-v1`, so this is only a safety net).

## Round 1 — confirmatory (dispatched 19:45 UTC)

Bases: `d1-aes_cipher-000` (model `model_holdout_aes_v2`, 24 runs without AES),
`d1-picorv32-016`, `d1-picorv32-006` (model `model_holdout_picorv32_v2`, 24 runs without
PicoRV32). Arms: rerun, uni30, uni50, uni70, tgt030-70, tgt050-70, tgt050-80,
tier020-80_050-50. Results are appended below as they land, with no post-hoc arm selection.

*(pending)*
