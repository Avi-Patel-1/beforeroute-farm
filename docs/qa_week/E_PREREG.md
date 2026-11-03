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

## Clarifications, 2026-11-03 03:33Z (before any packet reached a reader and before any rebuild existed)
Made after Codex's independent audits (AUDIT_PREREG_E, AUDIT_PACKET_FORMAT, AUDIT_HOLDOUT_E, AUDIT_SMOKE_E). No
prediction, test, threshold, source or chain rule above is changed; these fix wording elsewhere and pin down cases the
text above left implicit.
1. **Kept clock.** The definition above governs: the source counts as a run of the chain, so a passing source whose
   rebuilds all fail keeps its own target (source-only kept clock). The outbox PACKET_FORMAT.md said "none if no rebuild
   passed"; it is corrected. The contract.json text and the reader prompts already used this definition.
2. **Label states.** (i) first rebuild landed with metrics: pass1 by the judge, C1 and the slope defined; (ii) first
   rebuild ran but left no final metrics (a flow failure, recorded with its exit code): pass1 = fail, C1 and the slope
   **undefined** (never set to 0; excluded from slope error and counted), and the chain steps back to R1 + 0.05 as rule
   3 says; (iii) infrastructure loss (job or artifact lost, no chain record) after the one registered re-dispatch: the
   source is "not checked", excluded from every metric and listed. A null kept clock (no run of the chain passed, the
   source included) is a label value, distinct from (ii) and (iii). A missing or invalid prediction file counts as an
   abstention with p_pass 0.5 for pass/fail and Brier; its slope and kept clock are missing (not imputed) and counted.
   Fixtures committed: farm/qa/E/fixtures/test_score.py (source-only kept, no pass, no-metrics first rebuild, not
   landed, invalid prediction) and test_chain.py (runner-side chain = the baselines' chain simulation).
3. **Baseline probabilities.** The scripted baselines (raw claim, law, I/O rule, two-point line, hand-picked feature)
   are deterministic: p_pass = 1.0 when their response gives C(R1) ≤ R1, else 0.0; the Brier score uses exactly these.
4. **What the law has seen.** The law's constants s⁻ 0.59 / s⁺ 0.29 were fitted on the 328-run audit, which contains
   older runs of all four test families (other settings and targets, never these rebuild targets). For the law (and the
   two-point line, which uses a record run of the same setting) the test is therefore prediction of fresh rebuild
   targets of previously seen designs, not of wholly unseen designs; it is reported that way.
5. **Ties.** "Ties" under McNemar means no significant difference at α 0.05 over 35 sources, not equivalence. The four
   families are the replication units; per-family results are reported beside the pooled ones.
6. **Codex's arm** is a same-packet deterministic comparator: it may read any rung-2 file, but its training data lack
   layout/STA files, so in practice it uses the fields common to training and test packets.
7. **Electrical bar.** drv_bar differs by family; it is part of the judge, so it stays in the contract. Packets of one
   family are recognizable as such from their netlists anyway; each reader sees one packet and every predictor is run
   one packet at a time.
8. **Leak test.** Strengthened before any hand-over: only allowlisted packet paths may exist, MANIFEST.json must match
   every file's SHA-256, every .gz is decompressed, and each run starts with a self-test that plants leaks (design and
   port names inside a gzipped dump, a /work/ path inside a gzipped STA report, an unlisted file) and must catch all of
   them. farm/qa/E/verify_packets.py checks that net names agree across dumps, connectivity, DEF and SPEF, that SPEF
   units are NS/PF/OHM, DEF units 1000/µm, and the 9 corners.
9. **Ordering.** The lock commit with every prediction precedes the creation of the chain workflow run; E_RESULT.md will
   state both timestamps (commit time and the run's createdAt).
10. **Source count.** The outbox HOLDOUT_E.md said 36 sources (9 per family); the registered count is 35 (wbqspiflash 8),
    `farm/qa/E/sources.json` SHA-256 0bbcc3f668c4bce4dff91fd3c152164e60dac12ed86fd93bba714d7b142a51f3 (commit c99b6fb).
11. **Stratum counts (2026-11-03 04:10Z).** The sources paragraph above says "(16 tight, 12 loose, 7 very loose)"; the
    registered table and `sources.json` give 15 tight, 12 loose and 8 very loose (wbqspiflash: 3 tight, 3 loose, 2 very
    loose). The table and the selection script govern; only the prose sum was wrong. All 35 capture runs reproduced
    their record runs exactly (worst setup slack identical to every digit); 20 sources pass the judge (all loose ones).

## Clarification 12, 2026-11-03 05:05Z: fail-closed bug fixes, made before any label existed
Made after Codex's audit (findings on br/run_job.py, farm/qa/E/make_chains.py, run_predictor.py, verify_packets.py and
phase2.py). At this time no rebuild-chain job (`erk-*`) had been created: the branch's only workflow runs are the
capture smoke 41565377087, the 35 sources 41566168637 and the training-design chain smoke 41575897220. **No prediction,
test, threshold, source, chain rule or judge definition is changed;** the code is brought in line with the definitions
above and made fail-closed: missing data is never a pass.
1. **Judge admission** (`br/run_job.py e_judge`, used by the runner-side chain and by make_chains.py): a run passes only
   if setup WS, hold WS, route DRC, max-slew count and max-cap count are all present as finite numbers and meet the
   judge, and the electrical bar is a number. Before the fix a missing DRC or slew/cap count was read as 0, i.e. a pass
   on missing data. Effect on actual data: none. Every record run with final timing (3,119 on disk at 05:00Z) carries
   all five fields as finite numbers, and re-running make_chains.py with the fixed judge reproduces all 35 chain specs
   and chains.json byte for byte (20 passing sources, unchanged). A rebuild that lands its timing but lacks another
   judge field fails pass1; its claim and slope stay defined (they come from the timing) and the missing field is
   recorded.
2. **Label states, executable** (clarification 2): a rebuild with no final setup WS, its flow exit code recorded (a
   flow failure, including a per-flow timeout, exit −9), is state (ii): fail, slope undefined, step back. A rebuild that
   leaves neither metrics nor a job record (the worker died; no exit code was ever recorded) is infrastructure, state
   (iii): the runner writes no chain.json (only chain_partial.json, never scored) and exits 3; the job is re-dispatched
   once, as registered. A chain spec lacking T0, C0, the bar or source_pass is refused before any build.
3. **Frozen predictors** (`run_predictor.py`): every inference file is hashed (entry and dependencies; a missing or
   different digest refuses) and only the verified copies are importable; the expected packets are the 35 main packets
   of the committed packets_manifest.sha256, each rung-2 view verified file by file against its MANIFEST.json; any
   error, invalid or non-deterministic output, or file access outside the predictor's copies, its packet and the Python
   installation exits non-zero and writes nothing to the predictions folder (error records, if promoted, are
   abstentions by clarification 2). Before, the runner exited 0 with errors and hashed only the entry module.
4. **Packet verification** (`verify_packets.py`): at each RC corner every net with at least one load must have a SPEF
   D_NET with total capacitance > 0; the three corners must extract the same nets with total capacitance min < nom <
   max; every per-net dump row must carry a finite capacitance at all 9 corners; coverage is printed per corner. Before,
   an empty SPEF with valid units passed. All 47 rung-2 views pass: 100% of wired nets populated at every corner (the
   picorv32 packets' 67 load-less input ports carry no parasitics; the 6 shuffled views withhold layout by design).
5. **Lock and dispatch** (`phase2.py`): the lock refuses unless a preflight shows every required record present (35 per
   main arm, 19 two-point, 6 + 6 controls; invalid replies listed as the registered abstentions; reader audits and
   models reported, never dropped) and no job named erk-* exists on the branch; it commits PREFLIGHT.json and the
   predictor receipts and reads the lock commit's server push time (GitHub repository activity API). Dispatch
   re-verifies the lock commit's files against its manifest, the locked preflight, the absence of label jobs and of any
   other active run, and records the chain run's createdAt, which must be later than the lock push.
Fixtures: `farm/qa/E/fixtures/test_failclosed.py` (new; it fails on the pre-fix code), `test_chain.py` (its fake flow
now writes the slew/cap counts a real flow writes; same expectations), `test_score.py` (unchanged). The runner-side
chain smoke on training designs is re-run on the fixed code (E_SMOKE.md).
