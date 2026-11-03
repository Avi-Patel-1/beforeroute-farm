# Addendum 42 (E) — result: reading the chip. Can one finished run's record predict how the tools respond when the clock target moves?

**Final.** Scored 2026-11-03 09:16:57Z (`score.py` on the locked predictions), when all 35 registered rebuild chains had
landed (workflow run 41588658336, completed 09:15:19Z). Nothing is running.
- Pre-registration: docs/qa_week/E_PREREG.md on branch `qa-e-reading`. Hash lines in farm/prereg_hashes.txt: first
  ae1b4b20… (c6f07ac, pushed 02:26:45Z); clarifications 1–10 32d6c803… (bb1eb92); 11 58dff5af… (4505822); 12
  bbb26df2… (593a9e4, pushed 05:00:05Z: fail-closed bug fixes, made before any label existed). No prediction, test or
  rule changed after the first hash.
- **Predictions locked** at commit `9e1ccc7` (311 records, all valid; **server push 06:14:24Z**). **The labels' workflow
  run was created at 06:14:40Z**, 16 s later, at that same commit. The chronology is below.
- Scorer `farm/qa/E/score.py`, unchanged since 8d51a7a (before any rebuild). Tables by `farm/qa/E/report.py
  --aggregate-only` (e13fa02, committed before any label was read).
- **Aggregate rows only.** Codex asked that no per-case output reach a baseline author, so this file has no per-source
  rows. Per-source labels, chain records and the full report are private: `reading/private/{chains/, score.json,
  E_report_full.md}`. The packet key is committed by hash only (lock commit, `HASHES_PRIVATE.txt`); committing it is
  Avi's call.

## Bottom line
- **R1 (rung 1, the summary reader): does not hold** (1 of 3 parts).
  - It ties the law on pass/fail: 25 vs 29 correct, exact McNemar p = 0.125. Its 7 abstentions count as not correct.
  - It **beats** the law on kept clock: median error 6.7% vs 12.2%. The prediction said "ties or loses".
  - On the 19 two-point sources its false passes equal the two-point line's (0 vs 0). The prediction said "more".
- **R2 (rung 2, the raw-record reader with a Python sandbox): holds** (3 of 3 parts).
  - (i) Its median slope error is 0.119, against rung 1's 0.133, and it does not lose to rung 1 on pass/fail (2 vs 2).
  - (ii) It ties the law on pass/fail: 25 vs 29 correct, p = 0.22.
  - (iii) Its slope error is **0.72×** the law's (0.119 vs 0.165); the bar was ≤ 0.80.
  - The false-pass count belongs beside it: rung 2 called 22 passes and 3 were false. The law called 20 with 1 false;
    rung 1 called 17 with none false.
- **R3 (rung 3, a written formula learned on training designs): does not hold** (1 of 2 parts).
  - Its slope error is **1.42×** the law's (0.234 vs 0.165); the bar was ≤ 0.75.
  - It does beat the hand-picked feature (0.234 vs 0.278).
  - The frozen formula reads only contract fields, no per-net data (see Caveats).
- **Kept clock is where reading paid off most.** Rung 2's median error was **3.7%** (p90 24.8%), the best of every
  arm. The law's was 12.2% (p90 100%): it forecasts "no clock passes" for several chains that did keep one.
- **Pass/fail: nothing beat the slack sign.**
  - The law, rung 3, the hand-picked feature and Codex's comparator made the same 35 calls: 29 correct, 1 false pass,
    5 missed passes. That is the source run's slack sign (positive → pass).
  - No arm differs significantly from the law on pass/fail.
- **Codex's deterministic comparator** (registered as an arm; no prediction was made about it):
  - Same pass/fail calls as the law, and the best Brier score (0.116).
  - The largest slope error (0.301) and kept-clock error (33.2%) of all arms.
- **Controls.**
  - Renaming (same packet, new pseudonyms, fresh reader): same call 5/6, median |Δslope| 0.022.
  - Shuffled view (per-net fields permuted, layout withheld): same call 6/6, median |Δslope| 0.036.
  - With n = 6, a shuffling effect cannot be told apart from reader-to-reader variation.
- **Scale.** 35 sources from 4 design families (8–9 each); sources within a family are not independent. "Ties" means no
  significant difference at α 0.05, not equivalence.

## Q&A line (if asked "can an LLM predict the rebuild instead of running it?")
> "We pre-registered it and locked every forecast in git before any rebuild ran: GitHub shows the lock pushed 16 seconds
> before the rebuild run was created. Claude, reading one routed run's raw record, forecast how the claim moves with the
> target about 28 percent better than our fitted law, and its forecasts of the clock the chain finally keeps were the
> closest of any method, about 4 percent median error. But on the yes/no question — will the first rebuild pass — nobody
> beat the one-line rule 'negative slack fails'. So the rebuild still decides."

If pushed on "isn't the reader just doing the I/O arithmetic?":
*"Partly. A one-line I/O rule got within 16 percent of the reader on slope error. The reader's real edge is the kept
clock, 3.7 against 6.9 percent, with a third of the I/O rule's false passes (3 against 9)."*

Do not say:
- "Claude predicts timing better than the law", unqualified. On pass/fail rung 2 was numerically worse (25 vs 29
  correct, 3 false passes vs 1), though not significantly.
- "Reading the raw layout beat the summaries decisively". Slope error was 0.119 vs 0.133, and pass/fail tied 2–2.
  Rung 1 alone reached 0.81× the law's slope error.
- "A learned formula beats the law". R3 failed: 1.42×.
- "Significant", or anything stronger than the registered tests: 35 sources, 4 families.
- "Predicts unseen designs" for the law or the two-point line. The law's constants were fitted on older runs of these
  families (clarification 4).
- "The per-net data drove it". The shuffled-view diagnostic moved slopes by a median 0.036, and the renaming control
  (no information change) moved them by 0.022; both n = 6.
- "28% better than every scripted rule". The I/O rule's slope error was 0.141, so rung 2's edge over it is 16%.

## Prediction before rebuild: the timestamps
Server push times come from GitHub's repository activity API for `refs/heads/qa-e-reading`; run and job times from the
Actions API. Committer timestamps are given only beside them.

| event | commit / run | server time (UTC, Nov 3) |
|---|---|---|
| pre-registration hashed (first) | c6a5214, hash line c6f07ac | pushed 02:26:45Z |
| 35 capture sources (the specimens the readers saw) | run 41566168637 | 02:26:52Z–04:03Z |
| clarifications 1–10 after Codex's audits | 1115861, hash line bb1eb92 | pushed 03:33:19Z |
| rung 3's formula frozen (SHA-256 d6a64c83…) | 7edebc5 | pushed 03:54:42Z |
| packet MANIFEST hashes (82 views) | a5b6b24 | pushed 04:06:43Z |
| Codex's comparator sealed on Avi's Mac | local seal | 04:09:46Z (23:09:46 ET) |
| first blind reader started | coordinator | ≈ 04:13Z |
| clarification 12 (fail-closed fixes) | e61fc43 + b0a51c5, hash line 593a9e4 | pushed 04:59:53Z / 05:00:05Z |
| Codex's comparator frozen on the branch (hashes only) | 6d5f0ff | pushed 05:00:44Z |
| Codex's comparator run on the 35 packets | run_predictor receipt | 05:00:48–05:01:13Z |
| rung 3 run on the 35 packets | run_predictor receipt | 05:01Z |
| **lock: all 311 predictions, prompts, predictor receipts, key check** | **9e1ccc7** (committer 06:14:21Z) | **pushed 06:14:24Z** |
| **chain run created (the labels)** | **41588658336** (head = 9e1ccc7) | **06:14:40Z** (first job started 06:14:43Z) |
| chain run completed | 41588658336 | 09:15:19Z |

- `phase2.py evidence` checks the chronology: `valid_chronology` true. There is exactly one run with chain jobs, its
  head contains the lock, all 35 tags ran exactly once, and there were no re-runs or re-dispatches. It also confirms no
  job named `erk-*` existed before the lock.
- The workflow and runner were pinned at the run's head: `.github/workflows/farm.yml` blob 7f98eef (SHA-256
  4685981b…), `br/run_job.py` blob 0a23235 (97152e50…), `farm/qa/E/chains.json` blob 311a032 (626440ca…).
- The lock commit's 323 files match its MANIFEST.sha256 (5db2a0e8…). The predictions scored here are byte-identical
  to the locked ones.
- The label-free lock receipt for Codex is in the outbox (`RECEIPT_E_LOCK.md`); Codex verified it.

## What ran
- **Chain run 41588658336** (farm.yml, one job per source, at most 4 at once, longest first by the source's own flow
  time; scheduling only): 35/35 jobs succeeded, 06:14:40Z–09:15:19Z.
  - 99 rebuilds: zipdiv 31, cic_decimator 25, wbqspiflash 22, picorv32 21; 73 passed the judge and 26 failed.
  - Every rebuild landed with all five judge fields. There were 0 flow failures, 0 missing fields and 0
    infrastructure losses, so no re-dispatch was needed.
  - 10.4 flow-hours and 11.8 job-hours; the longest job took 92 min.
- **Earlier runs on the branch** (smoke runs are excluded from every analysis): capture smoke 41565377087; the 35
  sources 41566168637; chain smokes 41575897220 and 41581313357, the second a re-run on the fail-closed code that
  matched the first rebuild for rebuild.
- **Predictors.** The coordinator ran 35 rung-1, 35 rung-2, 6 renaming and 6 shuffled-view readers, each a fresh
  Claude Opus 5.5 instance in an isolated sandbox with one packet; every transcript was audit-clean. Rung 3 and
  Codex's comparator went through `run_predictor.py` (every dependency hashed; packets checked against the committed
  manifest). The scripted baselines were written by E1; a re-run reproduced them byte for byte.
- Toolchain as registered: LibreLane 3.0.16 image `ghcr.io/librelane/librelane@sha256:4bc9042b…`, sky130A
  8afc8346…, `sky130_fd_sc_hd`, 9 STA corners.

## Setup (as registered)
- **Question.** Can one finished run's record predict how LibreLane responds when the clock target moves to the run's
  own claim?
  - Each of 35 sources is a search run of a held-out design family (zipdiv, cic_decimator, wbqspiflash, picorv32),
    re-run with full capture.
  - Every first-rebuild target is a clock its setting had never been run at. So the labels did not exist anywhere when
    the predictions were locked.
- **Claim** C = asked period T − worst setup slack over the 9 corners (AutoTuner's `effective_clk_period`). ceil05 =
  round up to 0.05 ns.
- **Judge (pass):** the flow completed; setup and hold worst slack ≥ 0 at all 9 corners; detailed-route DRC 0;
  max-slew + max-cap count (9 corners) ≤ the family's stock bar (zipdiv 295, cic_decimator 89, wbqspiflash 953,
  picorv32 2881). It is fail-closed: a missing field is never a pass.
- **Chain** (runner-side):
  - The first rebuild is at R1 = ceil05(C0).
  - After a pass, rebuild at ceil05(own claim) while that is below the smallest passing clock and above every failed
    clock below it.
  - After a failed first rebuild, step back once to max(ceil05(C1), R1 + 0.05).
  - At most 4 rebuilds; the source counts as a run of the chain.
- **Labels:** pass1 (the judge on the first rebuild); slope s = (C1 − C0)/(R1 − T0); kept clock K = the smallest passing
  clock of the chain, or none.
- **Arms** (all predict p_pass, a call, a slope and a kept clock):
  - Raw claim: C(T) = C0.
  - The law: F = T0 − k·WS0, k = 1/(1 − s), s⁻ 0.59 / s⁺ 0.29.
  - I/O-aware scalar rule.
  - Two-point line: only the 19 sources with a record second point; scored as its own tier.
  - Hand-picked feature: slope = 0.4288 − 0.9036·f.
  - Rung 1: the 6-line signoff summary, a 9-corner table and the contract; no tools.
  - Rung 2: the full pseudonymized raw record and a Python sandbox, ≤ 40 tool calls.
  - Rung 3: a formula written from the training families only, frozen before it saw a test packet.
  - Codex's comparator: trained on the training families, sealed 23:09 ET, run here blind.

## Registered tests (verbatim predictions in E_PREREG.md; computed by score.py)
| | prediction | part | result | part holds? |
|---|---|---|---|---|
| R1 | rung 1 ties or loses to the law on pass/fail and kept clock, and makes more false passes than the two-point line | pass/fail vs law | ties (rung 1 right & law wrong 0, reverse 4, p = 0.125) | yes |
| | | kept clock vs law | beats (median 6.7% vs 12.2%; > 1 point lower) | **no** |
| | | false passes on the 19 two-point sources | rung 1 0 vs two-point line 0 | **no** |
| | | **R1** | | **does not hold** |
| R2 | rung 2 beats rung 1, ties the law on pass/fail, beats the law on slope error by ≥ 20% | (i) slope error < rung 1's and no pass/fail loss to rung 1 | 0.119 < 0.133; pass/fail 2 vs 2, p = 1 | yes |
| | | (ii) pass/fail vs law | ties (1 vs 5, p = 0.22) | yes |
| | | (iii) slope error ≤ 0.80 × law's | 0.119 / 0.165 = 0.72 | yes |
| | | **R2** | | **holds** |
| R3 | rung 3 cuts slope error by ≥ 25% vs the law and beats the hand-picked feature | slope error ≤ 0.75 × law's | 0.234 / 0.165 = 1.42 | **no** |
| | | < hand-picked feature's | 0.234 < 0.278 | yes |
| | | **R3** | | **does not hold** |

What the outcomes mean, read with the pre-registration's own key:
- **R2 holds.** The raw record carries information about the flow's response that the law lacks, and slightly more
  than the summaries carry. The false-pass count stands beside it: rung 2 3/22, the law 1/20.
- **R1 failed in the readers' favour.** The summary reader already did better than predicted. Its slope error was
  0.81× the law's, and its kept clock beat the law's. So the summaries alone captured most of the gain over the law;
  the raw record added a little more (slope error 0.133 → 0.119, kept clock 6.7% → 3.7%).
- **R3 failed.** A formula learned on other designs did not transfer: it is worse than the law on slope. This formula
  used contract fields only.
- **The law is not prospectively confirmed on slope.** Both readers and the I/O rule beat it (0.165, against 0.119,
  0.133 and 0.141). On pass/fail its slack-sign calls tie every arm.

## Scoreboard (35 sources; aggregate)
| arm | false pass / called pass | missed / actual pass | abstain | correct / 35 | Brier | slope err median (mean) | kept err median (p90) [n = 28] | kept-vs-none agree |
|---|---|---|---|---|---|---|---|---|
| raw claim | 11/35 | 0/24 | 0 | 24 | 0.314 | 0.216 (0.366) | 7.7% (25.8%) | 28/35 |
| the law | 1/20 | 5/24 | 0 | 29 | 0.171 | 0.165 (0.317) | 12.2% (100%) | 27/35 |
| I/O rule | 9/33 | 0/24 | 0 | 26 | 0.257 | 0.141 (0.293) | 6.9% (19.9%) | 28/35 |
| hand-picked feature | 1/20 | 5/24 | 0 | 29 | 0.171 | 0.278 (0.323) | 18.1% (100%) | 27/35 |
| rung 1 | 0/17 | 3/24 | 7 | 25 | 0.120 | 0.133 (0.236) | 6.7% (100%) | 30/35 |
| **rung 2** | 3/22 | 2/24 | 5 | 25 | 0.127 | **0.119** (0.217) | **3.7%** (24.8%) | 30/35 |
| rung 3 | 1/20 | 5/24 | 0 | 29 | 0.132 | 0.234 (0.266) | 8.9% (100%) | 27/35 |
| Codex's comparator | 1/20 | 5/24 | 0 | 29 | **0.116** | 0.301 (0.296) | 33.2% (100%) | 27/35 |

- Every arm has 35 valid records. No reply was invalid, so there were no imputed abstentions. Abstaining readers
  still gave a slope and a kept clock, and those are scored.
- The **slope error** is |ŝ − s| per source, with 35 defined slopes (no first rebuild lacked metrics). The **kept
  error** is |K̂ − K|/K over the 28 chains that kept a clock; a null forecast scores 100%. Abstentions count as not
  correct and still enter the Brier score.
- Labels:
  - First rebuild passed 24/35: tight sources 5/15, loose 11/12, very loose 8/8.
  - 28 chains kept a clock and 7 kept none (all 7 tight). No chain kept only the source's own target.
  - Median measured slope 0.216 (range −0.18 to 1.23): tight 0.11, loose 0.28, very loose 0.18.

**Pass/fail comparisons** (exact McNemar on per-source correctness; only R1 and R2 use these as tests):
| A vs B | A right, B wrong | B right, A wrong | p | |
|---|---|---|---|---|
| rung 1 vs law | 0 | 4 | 0.125 | ties |
| rung 2 vs law | 1 | 5 | 0.219 | ties |
| rung 2 vs rung 1 | 2 | 2 | 1 | ties |
| rung 3, hand-picked, Codex vs law | 0 | 0 | 1 | identical calls |
| Codex vs rung 2 | 5 | 1 | 0.219 | ties |
| law vs raw claim | 10 | 5 | 0.302 | ties |
| I/O rule vs law | 5 | 8 | 0.581 | ties |

## Per family (the replication units; median slope error)
| arm | cic_decimator | picorv32 | wbqspiflash | zipdiv | equal-family median | pooled (registered) |
|---|---|---|---|---|---|---|
| raw claim | 0.341 | 0.205 | 0.231 | 0.179 | 0.218 | 0.216 |
| the law | 0.552 | 0.100 | 0.134 | 0.374 | 0.254 | 0.165 |
| I/O rule | 0.141 | 0.119 | 0.117 | 0.179 | 0.130 | 0.141 |
| hand-picked | 0.363 | 0.253 | 0.220 | 0.278 | 0.265 | 0.278 |
| rung 1 | 0.104 | 0.163 | 0.143 | 0.213 | 0.153 | 0.133 |
| rung 2 | 0.094 | 0.173 | 0.138 | 0.071 | 0.116 | 0.119 |
| rung 3 | 0.380 | 0.202 | 0.091 | 0.234 | 0.218 | 0.234 |
| Codex's comparator | 0.317 | 0.301 | 0.099 | 0.317 | 0.309 | 0.301 |

- The law's error is family-dependent: good on picorv32 and wbqspiflash (0.10, 0.13), poor on cic_decimator and
  zipdiv (0.55, 0.37).
- With equal family weights, rung 2's ratio to the law is 0.46, against 0.72 pooled.
- Rung 2 beats the law on slope in 2 of 4 families (cic_decimator, zipdiv), not on picorv32 or wbqspiflash. The
  pooled verdict leans on the two families where the law is weak.

## Two-point tier (the 19 sources with a record second point; every arm on the same subset)
The two-point line uses one more record run than any other arm, so it is scored only here.

| arm | false pass / called pass | missed / actual pass | correct / 19 | Brier | slope err median | kept err median [n = 15] |
|---|---|---|---|---|---|---|
| two-point line | 0/13 | 1/14 | 18 | 0.053 | 0.183 | 4.5% |
| the law | 0/13 | 1/14 | 18 | 0.053 | 0.156 | 11.5% |
| I/O rule | 3/17 | 0/14 | 16 | 0.158 | 0.179 | 10.3% |
| rung 1 | 0/12 | 1/14 | 16 (2 abstain) | 0.089 | 0.133 | 9.4% |
| rung 2 | 1/14 | 1/14 | 17 | 0.077 | 0.071 | 4.4% |
| rung 3 | 0/13 | 1/14 | 18 | 0.052 | 0.168 | 7.4% |
| Codex's comparator | 0/13 | 1/14 | 18 | 0.046 | 0.297 | 26.3% |
| raw claim / hand-picked | 5/19 / 0/13 | 0/14 / 1/14 | 14 / 18 | 0.263 / 0.053 | 0.233 / 0.250 | 9.9% / 14.7% |

On these 19, a second record point gives the two-point line a kept-clock error (4.5%) close to rung 2's (4.4%).
Rung 2's slope error there (0.071) is the lowest.

## Controls (diagnostics, no criterion; 6 pairs each)
- **Renaming control** (the same 6 packets re-pseudonymized with a new salt, read by fresh instances):
  - Same call 5/6; |Δp_pass| median 0.055 (max 0.24); |Δslope| median 0.022.
  - Slope error median on these 6: main readings 0.063, controls 0.106.
- **Shuffled-view diagnostic** (per-net geometric/electrical fields permuted among nets of the same driver cell and
  fanout, totals kept, layout withheld):
  - Same call 6/6; |Δp_pass| median 0.060 (max 0.29); |Δslope| median 0.036.
  - Slope error median: main 0.063, shuffled 0.105.
- The shuffle cost as much accuracy as a mere renaming did. With 6 pairs, these controls cannot show that the
  per-net fields themselves carried the rung-2 gain.

## Abstentions and reader audit
- Abstentions: rung 1 7 of 35, rung 2 5 of 35; 0 for the scripted arms, rung 3 and Codex.
- Invalid replies: none.
- All 82 reader transcripts were audit-clean (claude-opus-5-5). 13 readers read the harness's overflow copy of their own
  tool output; the coordinator verified each against that reader's transcript and recorded it. No reader read another
  packet.

## Predictions (E_PREREG.md) against outcome
| Prediction | Outcome | Held? |
|---|---|---|
| R1: rung 1 ties or loses to the law on pass/fail and kept clock, more false passes than the two-point line | ties on pass/fail; beats on kept clock; 0 vs 0 false passes | **no** |
| R2: rung 2 beats rung 1, ties the law on pass/fail, ≥ 20% lower slope error than the law | 0.119 < 0.133 (pass/fail tied); ties; 28% lower | **yes** |
| R3: rung 3 ≥ 25% lower slope error than the law and beats the hand-picked feature | 42% higher; beats the hand-picked feature | **no** |

## Caveats
1. **Four design families, 35 sources.** Sources within a family share a netlist and are not independent; the families
   are the replication units, and the per-family table shows the slope result is not uniform.
2. **"Ties" is not equivalence.** At 35 sources the McNemar test detects only large pass/fail differences. Rung 2's
   25 correct against the law's 29 is numerically worse.
3. **Pass/fail is nearly decided by the slack sign at these targets.** The sign rule gets 29 of 35. Readers abstained
   on 7 and 5 sources, which counts against them on correct calls (not on Brier).
4. **The law saw these families** (clarification 4). Its constants were fitted on an audit that includes older runs of
   all four test families. This tests fresh rebuild targets of seen designs, not unseen designs.
5. **Rung 3's formula reads contract fields only.** The rung-3 author (a fresh instance, audit-clean) chose contract
   fields, with no per-net data. R3's failure says that formula did not transfer. It is not a test of a formula over
   per-net raw fields.
6. **Codex's comparator ran on a different Python stack** (3.13.17, numpy 2.5.3; sealed on 3.12.0, numpy 2.4.2). A
   parity re-run on 3.12.0 / 2.4.2 gave 35/35 bit-identical records. Its training data had no layout or STA files, and
   only 6 training families met its eligibility rules.
7. **Medians over a skewed error distribution.** Means run 0.22–0.37. The registered tests use pooled medians; the
   equal-family medians are reported beside them.
8. **Pseudonyms remove names, not physics.** A reader could recognize a design's structure. The test families'
   *metrics* are public in the record; their rebuild labels were not.
9. **Training labels are historical; only these test labels are prospective.**

## Deviations and notes
- **Clarification 12** (04:59Z, before any label existed): fail-closed fixes to the judge admission, the chain's
  infrastructure-loss state, the predictor runner (every dependency hashed), packet verification (per-corner SPEF
  coverage) and the lock preflight. No prediction, test or rule changed. On the actual data the fixed judge changes
  nothing: the 35 chain specs were reproduced byte for byte, and the chain smoke matched rebuild for rebuild.
- Added after clarification 12 and before any label was read, at Codex's request:
  - `check_key.py` (the private key is consistent: 18/18 checks);
  - a runtime-parity re-run of Codex's comparator;
  - `phase2.py evidence` (server push time, pinned workflow and runner, duplicate and re-dispatch listing);
  - `report.py --aggregate-only`.
- The chains were dispatched longest-first. This is scheduling only: the jobs are independent and deterministic.
- The lock receipt gives the first job start as 06:14:42Z, a placeholder the jobs API shows for queued jobs. The
  first job actually started at 06:14:43Z. Both are after the push (06:14:24Z) and the run's creation (06:14:40Z).
- Re-running `baselines.py` for the reproducibility check rewrote `private/baselines_meta.json` with the same fit
  (a = 0.4288, b = −0.9036, n = 343).
- `score.py`'s console summary would crash if no source were checked (its JSON is written first). It was not triggered.

## Files
- docs/qa_week/E_PREREG.md, E_SMOKE.md, E_RESULT.md (this file).
- Branch qa-e-reading:
  - `farm/qa/E/` — score.py, report.py, phase2.py, run_predictor.py, check_key.py, verify_packets.py, make_chains.py,
    baselines.py, elib.py, epack.py, leak_test.py, fixtures/;
  - `farm/qa/E/locked/` — the lock: predictions, PREFLIGHT.json, predictor receipts, prompts, rung-3 formula, key
    check, Codex parity, MANIFEST.sha256, HASHES_PRIVATE.txt;
  - `farm/qa/E/frozen/` — rung 3's formula, and Codex's hashes;
  - `br/run_job.py` — the runner-side chain.
- Private (Avi / coordinator only): `/home/claude/ideas/overnight/reading/private/` — chains/ (35 chain records),
  score.json, E_report_full.md (per-source rows), lock_evidence_final.json, packet_key.json.
- Outbox: PREREG_E.md, SMOKE_E.md, RECEIPT_E_LOCK.md, RESULT_E.md (aggregate).
