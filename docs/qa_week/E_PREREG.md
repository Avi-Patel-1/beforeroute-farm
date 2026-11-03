# Addendum 42 (E) — pre-registration: reading the chip. Can one finished run's record predict how the tools respond when the clock target moves?

Written 2026-11-03 02:25Z (Nov 2, 21:25 ET) by the E1 agent of the overnight push, after the slides were locked
(Oct 30), **before any source run (tags `ers-*`) and before any rebuild (tags `erk-*`)**. Only the smoke run
`smoke-ers-xtea-01` (a training design; docs/qa_week/E_SMOKE.md) ran before this. Its SHA-256 is appended to
farm/prereg_hashes.txt on branch `qa-e-reading` before the source batch is dispatched. Avi did not see the split, the
source list or the hand-picked feature before launch; they were fixed by the rules below.

## Question
TrueClock's thesis: a tuner's *claimed clock* (target − worst setup slack) is a guess, because a new target builds a
different circuit. The weight-space post reads a network's behaviour from its raw weights without running it. Here a
fresh Claude reads one routed run's record, with zero new runs, and predicts how the flow responds when the target
moves to the run's own claim. **The design that makes it prospective:** the predictions are hashed and committed to
this branch *before* the rebuilds that label them are dispatched, so the GitHub timestamps prove they are not
hindsight. The labels do not exist anywhere yet: every source's first rebuild target is a clock its setting was never
run at.

## Toolchain (frozen; as every sky130 farm run)
LibreLane 3.0.16, image `ghcr.io/librelane/librelane@sha256:4bc9042ba177f73f275b5b39e7d372a07d3f4043f548a0ba7f640097b7205051`,
sky130A PDK 8afc8346a57fe1ab7934ba5a6056ea8b43078e71, `sky130_fd_sc_hd`; 9 STA corners ({min,nom,max} RC × {tt 25 °C 1.80 V,
ss 100 °C 1.60 V, ff −40 °C 1.95 V}); clock uncertainty 0.25 ns; derate ±5%; input and output delays 20% of the period
on every non-clock port. GitHub Actions `farm.yml` dispatched on this branch, `br/run_job.py` (this branch: adds the
`"capture": true` option, which copies files after the flow and changes nothing in it; smoke: all 293 metrics of a
replayed run identical). The flow is deterministic (replays bit-identical).

## Definitions
- **Claim** C = asked period T − worst setup slack WS over the 9 corners (AutoTuner's `effective_clk_period`).
- **ceil05(x)** = x rounded up to 0.05 ns (`farm/tune_a32.py ceil05`).
- **Judge (pass)**: the flow completed; setup WS ≥ 0 and hold WS ≥ 0 at all 9 corners; detailed-route DRC = 0;
  max-slew + max-cap violation count (9 corners summed) ≤ the design's stock bar (its LibreLane-defaults run at its
  default clock: zipdiv 295 (x6d-zipdiv-001), cic_decimator 89 (x6d-cic_decimator-006), wbqspiflash 953
  (x6d-wbqspiflash-001), picorv32 2881 (x1d-picorv32-001)) — the record's judge (`farm/tune.py outcome`). A rebuild
  without metrics fails.
- **Registered chain** (E5's rule at 0.05 ns; same settings, only CLOCK_PERIOD changes), from source S (T0, C0):
  1. first rebuild at R1 = ceil05(C0);
  2. after a passing rebuild with claim C: rebuild at ceil05(C) while that is below the chain's smallest passing clock
     and above every failed clock of the chain that lies below it;
  3. if the first rebuild fails: step back once, to max(ceil05(C1), R1 + 0.05), unless that is not below the chain's
     smallest passing clock; a failed rebuild after that ends the chain;
  4. at most 4 rebuilds. The source counts as a run of the chain (so a passing source's own target is a passing
     clock). A target already run in the chain reuses that result.
- **Labels per source:** (a) **pass1** = the judge on the first rebuild at R1; (b) **kept clock K** = the smallest
  passing clock of the chain, none if no run passed; (c) **slope** s = (C1 − C0)/(R1 − T0), C1 = the first rebuild's
  claim.

## Test designs (family-level split; `/mnt/user-data/outputs/overnight/outbox/HOLDOUT_E.md`)
Pool: the design families of the TrueClock search record (`results/tune*/state.json`) with median routed std-cell count
< 15,000 (RTL variants merged into their family): APU, cic_decimator, clip16, md5, ocs_blitter, picorv32, usb_cdc_core,
wbqspiflash, xtea, zipdiv. Sorted by SHA-256 of the family name, first 4: **zipdiv, cic_decimator, wbqspiflash,
picorv32** (held out). Training (rung 3, the hand-picked feature's fit, Codex's baseline): every other family (APU, PPU,
xtea, usb_cdc_core, clip16, md5, ocs_blitter, aes_cipher, bm64, y_huff, blabla, des, chacha, salsa20, sha512, ldpcenc,
point_add). No seed, arm, chain, closure or RTL variant of a test family enters any training or calibration data.

## Sources (35; `farm/qa/E/select_sources.py` → `farm/qa/E/sources.json`, job specs `farm/jobs/ers-*.json`)
Settings + targets taken from the record's search runs of the test families, re-run now with full capture (each spec
is a copy of the original run's spec plus `"capture": true`). Per family: candidates are completed runs of the original
RTL (not closure/chain re-runs), feasible apart from setup (DRC 0, hold ≥ 0, drv ≤ bar), whose R1 = ceil05(C0) was never
run for that setting in the record (label new) and |R1 − T0|/T0 ≥ 5%; strata by T0/C0: tight < 1, loose 1–1.3, very
loose ≥ 1.3, quotas 4/3/2; order: settings with ≥ 2 targets in the record first (they give the two-point line a second
point), then SHA-256 of the tag; one source per setting. wbqspiflash had only 3 tight candidates: **35 sources**
(16 tight, 12 loose, 7 very loose). If a capture run does not reproduce its record run, the capture run's own values
define C0 and R1 (it is the specimen the readers see) and the difference is reported.

| source | stratum | record run | T0 (ns) | C0 record | R1 | targets in record | second point |
|---|---|---|---|---|---|---|---|
| ers-zipdiv-01 | tight | xab2-zipdiv-003 | 9.28 | 12.559 | 12.60 | 2 | xaf2-zipdiv-001 |
| ers-zipdiv-02 | tight | x6d-zipdiv-003 | 13.36 | 14.159 | 14.20 | 7 | x7k-zipdiv-001 |
| ers-zipdiv-03 | tight | x8f-zipdiv-004 | 8.59 | 12.903 | 12.95 | 1 | — |
| ers-zipdiv-04 | tight | xab2-zipdiv-004 | 11.80 | 12.515 | 12.55 | 1 | — |
| ers-zipdiv-05 | loose | x6f-zipdiv-004 | 11.45 | 9.959 | 10.00 | 6 | x6f-zipdiv-005 |
| ers-zipdiv-06 | loose | xaf2-zipdiv-003 | 8.59 | 8.105 | 8.15 | 2 | xab2-zipdiv-001 |
| ers-zipdiv-07 | loose | xaf2-zipdiv-005 | 8.59 | 7.156 | 7.20 | 2 | xab2-zipdiv-005 |
| ers-zipdiv-08 | very loose | x6e-zipdiv-001 | 19.09 | 11.396 | 11.40 | 8 | x6e-zipdiv-002 |
| ers-zipdiv-09 | very loose | x6z-zipdiv-001 | 17.72 | 8.246 | 8.25 | 8 | x8a-zipdiv-005 |
| ers-cic_decimator-01 | tight | x6d-cic_decimator-008 | 7.00 | 8.005 | 8.05 | 8 | x6d-cic_decimator-009 |
| ers-cic_decimator-02 | tight | xab2-cic_decimator-001 | 5.45 | 7.773 | 7.80 | 2 | xaf2-cic_decimator-001 |
| ers-cic_decimator-03 | tight | x6z-cic_decimator-010 | 4.84 | 7.778 | 7.80 | 1 | — |
| ers-cic_decimator-04 | tight | x8f-cic_decimator-006 | 4.50 | 5.488 | 5.50 | 1 | — |
| ers-cic_decimator-05 | loose | xab1-cic_decimator-003 | 5.48 | 4.994 | 5.00 | 2 | xaf1-cic_decimator-001 |
| ers-cic_decimator-06 | loose | x8f-cic_decimator-001 | 4.50 | 4.199 | 4.20 | 2 | x8b-cic_decimator-001 |
| ers-cic_decimator-07 | loose | x6f-cic_decimator-001 | 10.00 | 8.847 | 8.85 | 6 | x6f-cic_decimator-002 |
| ers-cic_decimator-08 | very loose | xab1-cic_decimator-004 | 8.32 | 6.272 | 6.30 | 1 | — |
| ers-cic_decimator-09 | very loose | x8b-cic_decimator-003 | 8.13 | 5.829 | 5.85 | 1 | — |
| ers-wbqspiflash-01 | tight | x6d-wbqspiflash-004 | 11.32 | 13.085 | 13.10 | 7 | x7k-wbqspiflash-001 |
| ers-wbqspiflash-02 | tight | xaf2-wbqspiflash-007 | 8.49 | 9.061 | 9.10 | 1 | — |
| ers-wbqspiflash-03 | tight | xaf1-wbqspiflash-003 | 8.49 | 9.433 | 9.45 | 1 | — |
| ers-wbqspiflash-04 | loose | x6e-wbqspiflash-003 | 13.20 | 11.441 | 11.45 | 8 | x6e-wbqspiflash-004 |
| ers-wbqspiflash-05 | loose | x6f-wbqspiflash-003 | 13.20 | 10.880 | 10.90 | 6 | x6f-wbqspiflash-004 |
| ers-wbqspiflash-06 | loose | x8a-wbqspiflash-005 | 8.49 | 7.883 | 7.90 | 1 | — |
| ers-wbqspiflash-07 | very loose | xab1-wbqspiflash-001 | 18.28 | 10.312 | 10.35 | 2 | xaf1-wbqspiflash-001 |
| ers-wbqspiflash-08 | very loose | x8b-wbqspiflash-001 | 15.39 | 10.149 | 10.15 | 2 | x8f-wbqspiflash-001 |
| ers-picorv32-01 | tight | x1d-picorv32-003 | 17.50 | 20.271 | 20.30 | 7 | x7k-picorv32-001 |
| ers-picorv32-02 | tight | x1r-picorv32-016 | 12.68 | 15.230 | 15.25 | 1 | — |
| ers-picorv32-03 | tight | x4l-picorv32-003 | 12.60 | 13.503 | 13.55 | 1 | — |
| ers-picorv32-04 | tight | x3p-picorv32-002 | 15.61 | 16.572 | 16.60 | 1 | — |
| ers-picorv32-05 | loose | x1r-picorv32-023 | 12.76 | 11.174 | 11.20 | 1 | — |
| ers-picorv32-06 | loose | x3p-picorv32-011 | 13.99 | 11.714 | 11.75 | 1 | — |
| ers-picorv32-07 | loose | x1r-picorv32-020 | 18.47 | 17.166 | 17.20 | 1 | — |
| ers-picorv32-08 | very loose | x1e-picorv32-002 | 21.25 | 13.762 | 13.80 | 7 | x1e-picorv32-003 |
| ers-picorv32-09 | very loose | x3p-picorv32-022 | 16.00 | 11.940 | 11.95 | 1 | — |

19 sources have a second point (two-point line scoreboard). **Capture** per source run (artifact `result-ers-*`):
per-net dump after global route and at signoff, final DEF, SPEF at min/nom/max RC, mapped netlist, signoff SDC, the
post-route and post-global-route STA report trees, 9 `checks.rpt`, metrics, resolved config, flow log.

## Arms (every arm predicts, for every source: p_pass, a call pass/fail/abstain, slope, kept clock or none)
Packets: `/home/claude/ideas/overnight/reading/packets/<pseudonym>/` in format E1.0 (outbox `PACKET_FORMAT.md`):
design, module, port, net and instance names, file paths and tags replaced by per-packet pseudonyms; a leak test
(`farm/qa/E/leak_test.py`: greps every packet for every design name, port/module name of length ≥ 4, run tag and
outcome-file name) must pass before any packet is handed over.
1. **Raw claim** (script): C(T) = C0 → pass, slope 0, kept R1.
2. **The law** (script; the claim under test in mechanism-law.md §2, sky130 constants as registered there):
   F = T0 − k·WS0 with k = 1/(1 − s), s = s⁻ = 0.59 if WS0 < 0 (k ≈ 2.44) else s⁺ = 0.29 (k ≈ 1.41); response
   C(T) = F + s(T)·(T − F), s(T) = 0.59 for T < F, 0.29 for T ≥ F (so C(T0) = C0). pass1 iff C(R1) ≤ R1; slope
   = (C(R1) − C0)/(R1 − T0); kept clock = the registered chain simulated on C(T) (setup only).
3. **I/O-aware scalar rule** (script): hold each path's delay at the source; port paths' claims move 0.2 ns per ns of
   target, register-to-register claims do not move: C(T) = max(T0 − WS_r2r0, C0 + 0.2(T − T0)) if the source is
   port-limited (WS0 < WS_r2r0 − 1e-4), else C(T) = C0. pass1, slope, kept as for the law.
4. **Two-point line** (script; separate scoreboard, the 19 sources with a second point (T′, C′) from the record):
   C(T) = C0 + ŝ(T − T0), ŝ = (C0 − C′)/(T0 − T′).
5. **Rung 1** (Claude Opus 5.5, fresh instance per packet, one packet each): the rung-1 packet only (contract +
   `reports/summary.txt`: the 6-line signoff summary Claude read as a proposer in Addenda 32/35 + a 9-corner table);
   no code execution, no web, no repo.
6. **Rung 2** (fresh instance per packet): the full rung-2 packet (raw record: per-net dumps, DEF, SPEF, netlist, STA
   reports, metrics + the rung-1 content) and a Python sandbox over it; no web, no repo; ≤ 40 tool calls.
   - *Renaming control*: 6 packets (the first 6 pseudonyms in sorted order) re-packed with a different salt, read by
     fresh instances. Reported beside (prediction differences), no criterion.
   - *Shuffled-view diagnostic*: the same 6 packets with every per-net geometric/electrical field permuted among nets
     of the same driver cell and fanout (totals preserved), layout files withheld. Diagnostic only, never ground truth.
7. **Rung 3** (formula): a fresh Claude instance in `/home/claude/ideas/overnight/reading/rung3_train/` (training
   families' historical raw records + labels only) writes a Python function `predict(run_dir)` over raw fields
   present in both training and test packets; its file's SHA-256 is committed to this branch **before it sees any
   test packet**; the coordinator then runs it on the 35 rung-2 packets.
8. **Hand-picked feature** (rung 3's comparator; the plan's named example, *not chosen by Avi*): f = the number of
   signal nets in `nets/postgrt.jsonl.gz` whose `driver_slack_ns` (constrained, < 1e6) lies within 5% of the worst
   such slack (≤ min + 0.05·|min|), divided by the number of such nets; slope = a + b·f by least squares on the
   training labels (`labels.csv` rows); pass1 iff C0 + ŝ(R1 − T0) ≤ R1; kept by chain simulation. Fitted by script.
9. **Independent deterministic baseline (Codex)**: a no-LLM `predict(run_dir)` written by Codex on Avi's Mac from his
   own plan, trained only on `train_E/` (training families), frozen (SHA-256 of its files) by 05:00 ET Nov 3 and run by
   the coordinator on the blind rung-2 packets; its author never sees test labels. Registered as an arm; no
   prediction is made about it beyond the rung predictions.

**Lock.** All reader outputs (`/home/claude/ideas/overnight/reading/predictions/<arm>/<packet>.json`), the baselines'
outputs and the rung-3/Codex hashes are committed to this branch with a SHA-256 manifest **before** the rebuild-chain
workflow run is created. The chains run runner-side (one job per source, `farm/qa/E/chain_job.py`, ≤ 4 concurrent).

## Metrics (`farm/qa/E/score.py`, committed before any rebuild is dispatched; definitions here are binding)
Per arm over the 35 sources (two-point line: over its 19):
- **False passes** = call pass and pass1 false, reported as false passes / predicted passes; **missed passes** = call
  fail and pass1 true, / actual passes; **abstentions**; **correct calls** (abstain counts as not correct).
- **Brier** = mean (p_pass − pass1)² over all sources (abstaining does not exempt).
- **Slope error** = |ŝ − s|; median (primary) and mean.
- **Kept-clock error** over the sources whose chain kept a clock: |K̂ − K|/K, a null K̂ scores 1.0; median and p90;
  plus kept-vs-none agreement over all 35.
- **Comparisons.** Pass/fail: exact two-sided McNemar on per-source correctness, α = 0.05: "beats" = more correct and
  p < 0.05, "loses" = fewer and p < 0.05, else "ties". Kept clock: A beats B if A's median kept-clock error is lower
  by more than 1 percentage point, loses if higher by more than 1 point, else ties. Slope: as stated per prediction.
  Reported per family (equal-family medians) as well as pooled.

## Registered predictions (the reading ladder, copied verbatim) and their tests
- **R1 (rung 1):** "rung 1 (one run's timing-report summaries) ties or loses to the law on pass/fail and kept clock,
  and makes more false "pass" calls than the two-point line would". *Test:* rung 1 vs the law: McNemar result is
  "ties" or "loses" **and** kept-clock comparison is "ties" or "loses"; **and** on the 19 two-point sources rung 1's
  false passes > the two-point line's false passes. All three → R1 holds.
- **R2 (rung 2):** "rung 2 (one run's raw record + a Python sandbox) beats rung 1, ties the law on pass/fail, and beats
  the law on slope error by at least 20%". *Test:* (i) rung 2's median slope error < rung 1's and rung 2 does not
  lose to rung 1 on pass/fail (McNemar); (ii) rung 2 vs the law on pass/fail: "ties"; (iii) rung 2's median slope
  error ≤ 0.80 × the law's. All three → R2 holds.
- **R3 (rung 3):** "rung 3 (a written formula over raw fields, learned from training designs' historical raw records
  and outcomes only, registered before it sees any test design) cuts slope error on held-out designs by at least 25%
  vs the law and beats a hand-picked feature". *Test:* rung 3's median slope error ≤ 0.75 × the law's **and** < the
  hand-picked feature model's. Both → R3 holds.
Each part is reported separately whatever the verdict.

## What each outcome means
- R1 holds, R2 fails: a reader of reports adds nothing to one line of arithmetic, and the raw layout does not rescue
  it: the rebuild is irreducible ("rebuild, don't predict").
- R2 holds: the raw record carries information about the flow's response that the summaries and the law lack (say it
  with the false-pass count beside it).
- R3 holds and R2 fails: the information is in the raw fields, but a learned formula extracts it better than a reader.
- The law beating every reader on slope is the law's prospective confirmation (its constants were fitted on seen data;
  here they predict unseen designs).

## Budget, timing, handling
- Sources: 35 runs, about 3–5 flow-hours (picorv32 ~15 min each, others 1–8 min), one workflow run, ≤ 4 concurrent.
- Chains: ≤ 140 rebuilds, one job per source, ≤ 4 concurrent; dispatched only after the lock commit.
- Readers: 35 rung-1 + 35 rung-2 + 12 control instances + 1 rung-3 author.
- Infrastructure failure (runner lost, timeout, artifact missing): the same job is re-dispatched once with the same tag.
- Decision: scored when every chain has landed (or at Mon Nov 9 20:00 UTC on what has landed, sources without a
  landed first rebuild reported as not checked). Nothing in the sources, chain rule, judge, metrics or tests changes
  after this file is hashed; deviations are logged in E_RESULT.md with reasons.

## Caveats known in advance
- 4 test families, 35 sources, 8–9 per family: sources within a family are not independent.
- The test families are in the public record's *metrics* (their other runs), not their rebuild labels; pseudonyms
  remove names, not physics, and a reader could recognize a design's structure.
- Race designs' search runs are mostly loose (few tight candidates); tight sources are 16 of 35.
- The law's constants were fitted on the 328-run audit, which includes runs of the test families (not these labels).
- The training labels are historical (retrospective); only the test labels are prospective.
