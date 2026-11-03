# F — result: do the field's own published ORFS winners hold at the clocks they claim?

**Primary: final.** Decided 2026-11-03 09:25 UTC (04:25 ET), when all 14 registered replays and all 14 first rebuilds
had landed (`farm/qa/F/f_score.py score`). **Chains (descriptive): still running** in the continuation phase of
workflow run 41602153382; kept clocks are added when they land.
- Pre-registration: docs/qa_week/F_PREREG.md, SHA-256 `ba4d15109bc56427de4bf28fb4f5ee37735b42724ea1599f39cf9014127edc05`,
  committed 3932f94 (code frozen) and recorded in farm/prereg_hashes.txt (ae9fc3e, 03:56:42Z) before the first
  registered run (f0c3667, 03:56:58Z).
- Analysis output: farm/qa/F/f_score_primary.json (sha256 f1bb8317…), tables from farm/qa/F/f_report.py. Timeline and
  the one deviation: docs/qa_week/F_LOG.md.

## Bottom line
- **The published winners reproduce exactly.**
  - All 14 configurations were built as published, at their published target, in the publication's own pinned image
    and harness. Each one returned its published claimed clock to the printed precision (largest gap 0.00004 %).
  - The 3 ORFS-agent database rows are bit-identical to the published rows on every metric they record.
  - Sources: 11 final agent submissions from EDA-env (ICCAD 2026) and the 3 best runs of ORFS-agent's published run
    database.
- **6 of the 14 fail at the clock they claim** (registered P2: holds). Rebuilt with the clock set to the claim
  (rounded up to 5 ps or 0.05 ns), they missed setup. All 6 misses are setup misses; one (EDA-env 008) also misses hold:
  - EDA-env 008 (jpeg): 2.1 ps;
  - EDA-env 016 (jpeg): 1.3 ps;
  - EDA-env 074 (mult16): 0.6 ps;
  - ORFS-agent aes/asap7: 23.6 ps;
  - ORFS-agent ibex/asap7: 97.1 ps;
  - ORFS-agent aes/sky130hd: 0.171 ns.
- **But the typical claim is not optimistic** (registered P1: fails).
  - The median change from the replay's claim to the first rebuild's own claim (d1) is **−1.5 %**: the rebuild claims a
    faster clock. The plan predicted ≥ +3 %.
  - 8 of the 14 held at their claim, and their rebuilds claimed 1.3–5.0 % faster still.
  - A negative d1 is itself only a claim (the rebuild's slack at R1), not a measured faster clock. Only the chains,
    which rebuild at those new claims, can show a faster clock that holds.
- **Registered verdict: the plan's prediction FAILS** ("median claim optimistic by ≥ 3 %, and at least one published
  winner fails at its claim": the second half holds, the first does not). This is the outcome the PREREG called
  "P2 without P1": the bias is design-, flow- and regime-dependent, and only a rebuild tells you which case a claim is in.
- **The sign follows the shared law, as the PREREG noted it would** (reported beside, no criterion):

| claim came from a run that… | n | first rebuild fails | median d1 |
|---|---|---|---|
| **missed** timing at its target | 4 | **4 of 4** | **+5.9 %** |
| **met** timing at its target | 10 | 2 of 10 (by 1.3 and 0.6 ps) | **−2.7 %** |

## Q&A line (if asked "do other people's AI winners hold up?")
> "I rebuilt the field's own published winners: eleven final submissions from EDA-env at ICCAD this year and the three
> best runs in ORFS-agent's published database. Every one reproduced exactly. Then I rebuilt each at the clock it
> claimed. Six of fourteen failed there: all four whose claim came from a run that missed timing, by 5 to 8 percent for
> ORFS-agent's, and two more by about a picosecond. The other eight held at their claim. So the score is wrong in
> both directions: too fast when it comes from a failing run, and conservative when it comes from a passing one."

If pushed on "so the claims were mostly fine?": *"The typical claim was fine; the AutoTuner-style ones were not. Every
claim that came from a run that missed timing was too fast: ORFS-agent's best runs by 6 to 8 percent. The claims that
came from runs that met timing were conservative by about 3 percent. My registered prediction was a 3 percent
overclaim across the board, and it failed."*

Do not say:
- "most published winners fail": 6 of 14 failed;
- "the field's claims are optimistic" without the sign split: the median was 1.5 % pessimistic;
- "EDA-env's headline is wrong": its headline (task 001, 291.5 ps) **held**. Rebuilt at 295 ps it passed with
  +7.4 ps, with an own claim of 287.6 ps;
- "the paper's ORFS-agent winners failed": the three rows are the best runs of the authors' published run database,
  not the runs behind the paper's tables (whose knob values are not published);
- anything about significance: 14 winners, 11 from one agent on one benchmark, several sharing a design.

## What ran
- **Registered batch r01**, workflow run 41575196054 (f0c3667):
  - primaries landed for 7 groups: ee008, ee016, ee011, oa-aes-s130, oa-aes-a7, oa-ibex-a7, ee001;
  - cancelled at 03:12 ET after Zenodo started returning HTTP 503 (see Deviations).
- **Retry batch r01b**, run 41602153382 (2605db9), under the PREREG's infrastructure rule:
  - the other 7 EDA-env groups, same tags, all landed;
  - then the continuation of all 14 chains (still running at the time of writing).
- **Primary-phase flows: 28** (14 replays, 14 first rebuilds); every one completed with metrics. Flow time about
  9.8 h (jpeg 46–61 min, sky130hd aes 35–41 min, ibex 24–45 min, aes 12–19 min, the small designs 2–6 min).
- **Runners:** GitHub Actions ubuntu-latest (4 vCPU), at most 2 jobs at once.
- **Images:**
  - EDA-env: built from its own Dockerfile, `openroad/orfs:26Q3-5-gfb65d5b48@sha256:699820f9…` plus its patched
    scripts;
  - ORFS-agent: `openroad/orfs:v3.0-1548-gce8d36a7@sha256:6fe655d0…`.
- **Smoke runs** (not analyzed): s01–s04, see SMOKE_F.md and the PREREG.

## Primary: the 14 published winners, replayed and rebuilt at their claim
T0 = published target (EDA-env: its evaluation clock). Claim = asked period − worst setup slack after route. R1 =
ceil(replay claim) on the grid. d1 = the first rebuild's own claim ÷ the replay's claim − 1 (positive = the published
claim was too fast). Units ps (asap7), ns (sky130hd).

| config | source / design | T0 (flow asked) | published claim | replay claim | first rebuild at R1 | its setup slack | its claim | d1 | judge at R1 |
|---|---|---|---|---|---|---|---|---|---|
| ee001 | EDA-env 001 aes | 385.5 (380) | 291.529 | 291.529 | 295 | +7.4 | 287.6 | −1.3 % | pass |
| ee008 | EDA-env 008 jpeg | 400 (400) | 530.690 | 530.690 | 535 | **−2.1** | 537.1 | +1.2 % | **FAIL** (setup; hold −0.8) |
| ee011 | EDA-env 011 ibex | 1000 (1000) | 953.681 | 953.681 | 955 | +29.6 | 925.4 | −3.0 % | pass |
| ee013 | EDA-env 013 aes | 368.2 (380) | 354.247 | 354.247 | 355 | +12.8 | 342.2 | −3.4 % | pass |
| ee016 | EDA-env 016 jpeg | 560.5 (400) | 508.927 | 508.927 | 510 | **−1.3** | 511.3 | +0.5 % | **FAIL** (setup) |
| ee037 | EDA-env 037 sboxpipe | 312 (400) | 176.510 | 176.510 | 180 | +9.7 | 170.3 | −3.5 % | pass |
| ee054 | EDA-env 054 aes | 340 (380) | 309.946 | 309.946 | 310 | +15.7 | 294.3 | −5.0 % | pass |
| ee074 | EDA-env 074 mult16 | 653 (900) | 401.527 | 401.527 | 405 | **−0.6** | 405.6 | +1.0 % | **FAIL** (setup) |
| ee075 | EDA-env 075 adder64 | 360 (400) | 222.743 | 222.743 | 225 | +7.8 | 217.2 | −2.5 % | pass |
| ee087 | EDA-env 087 mult16 | 615 (900) | 462.727 | 462.727 | 465 | +20.7 | 444.3 | −4.0 % | pass |
| ee097 | EDA-env 097 aes | 340 (380) | 327.695 | 327.695 | 330 | +7.7 | 322.3 | −1.7 % | pass |
| oa-aes-a7 | ORFS-agent row 744, aes | 140.237 | 427.663 | 427.663 | 430 | **−23.6** | 453.6 | +6.1 % | **FAIL** (setup; reg-to-reg) |
| oa-ibex-a7 | ORFS-agent row 1876, ibex | 604.088 | 1254.219 | 1254.219 | 1255 | **−97.1** | 1352.1 | +7.8 % | **FAIL** (setup; worst path to an output port, reg-to-reg also −72.5) |
| oa-aes-s130 | ORFS-agent row 2551, aes/sky130hd | 3.3 | 3.801 | 3.801 | 3.85 | **−0.171** | 4.021 | +5.8 % | **FAIL** (setup; reg-to-reg) |

## Registered test (f_score.py)
- **Population:** P = 14 of 14. Every replay is within 0.00004 % of the published claim; the registered tolerance was
  2 %.
- **P1:** median d1 = **−1.50 %** (needs ≥ +3 %). **Fails.**
- **P2:** 6 of 14 first rebuilds fail the judge (setup ≥ 0, hold ≥ 0, DRC 0 at R1). **Holds.**
  - Judged on setup alone, the same 6 fail.
  - No failure was a flow error; every rebuild had DRC 0.
- **Verdict: the prediction fails** (P1). Not underpowered (|P| = 14).

## Reported beside (as registered, no criterion)
| split | n | first-rebuild fails | median d1 |
|---|---|---|---|
| ORFS-agent | 3 | 3 | +6.1 % |
| EDA-env | 11 | 3 | −2.5 % |
| replay slack < 0 at T0 | 4 | 4 | +5.9 % |
| replay slack ≥ 0 at T0 | 10 | 2 | −2.7 % |

- d1 against the published claim (C1/C0_pub − 1): median −1.5 %, identical to d1 because every replay was exact.
- How far the failures missed, as a share of the rebuild clock:
  - ORFS-agent: 4.4–7.7 %;
  - EDA-env: 0.15–0.39 %, inside one 5 ps grid step.
- **The rebuild changes the clock the flow is asked for, in both directions.**
  - For the 4 claims from failing runs, the rebuild asks a looser clock than the published run did. Each came out
    slower than its claim.
  - For EDA-env task 016, the flow had been asked for 400 ps (the task's working SDC) while the claim (508.9) was
    judged at 560.5. The rebuild therefore asked 510, again looser, and it missed by 1.3 ps.
  - For the other 9 EDA-env claims, the rebuild asked a tighter clock than the published flow did. 8 passed;
    074 missed by 0.6 ps.

**Exploratory (post hoc, not registered): which clock was the flow actually asked for?**
- Split instead by whether the claim is slower or faster than the clock the **flow itself** was asked for (the
  working SDC for EDA-env).
- Claims slower than the flow's ask (n = 5: the four above plus 016): **5 of 5 fail**, median d1 **+5.8 %**.
- Claims faster than it (n = 9): 1 of 9 fails (by 0.6 ps), median d1 **−3.0 %**.
- This is the shared law's two-sign shape, read against the clock the flow saw rather than the clock the score
  used. It was found after looking, so it is a hypothesis for the next registration, not a result.

## Chains (descriptive; E5's rule, ≤ 4 rebuilds; continuing in run 41602153382)
After the primary phase, each chain continues:
- failed first rebuilds step back once:
  - ee008 to 540; ee016 to 515; ee074 to 410;
  - oa-aes-a7 to 455; oa-ibex-a7 to 1355; oa-aes-s130 to 4.05 ns;
- passing ones rebuild at their new claim:
  - ee001 to 290; ee011 to 930; ee013 to 345; ee037 to 175;
  - ee054 to 295; ee075 to 220; ee087 to 445; ee097 to 325.

Landed so far (each chain: every clock tried, pass/fail; units as above):

| config | chain after the replay | outcome |
|---|---|---|
| ee016 | 510 fail (−1.3), **515 fail (−35.3; own claim 550.3)** | ends with no passing rebuild near the claim: the flow is not monotonic in the clock. Only the replay passed, at the evaluation clock 560.5 with the flow asked for 400 |
| ee008 | 535 fail (setup −2.1, hold −0.8), **540: setup +10.4 (own claim 529.6) but hold −0.27** | ends with no pass under the registered judge (setup + hold). Judged on setup alone, it would keep 540 ps, 1.8 % above its claim |
| oa-aes-s130 | 3.85 fail (−0.171); 4.05: flow completed but its result was lost to a path bug in the continuation phase (F_LOG.md) | rerun in batch r01c |

(E5's convention counts the replay's own target as the kept clock where the replay met timing; for EDA-env that
target is the evaluation clock, not the clock the flow was asked for, so kept clocks are shown as chains here.)
Rows are added as the continuation phase lands.

## Predictions (F_PREREG.md) against outcome
| Prediction | Outcome | Held? |
|---|---|---|
| Median claim optimistic by ≥ 3 % (P1) | median d1 −1.5 % | **no** |
| At least one published winner fails at its claim (P2) | 6 of 14 fail | yes |
| (context in the PREREG, not a prediction) the law points against P1 on this population (10 of 14 claims from passing runs) and towards P2 | as described: missed-timing claims 4/4 fail, +5.9 %; met-timing claims −2.7 % | — |

## Independent audit (Codex, AUDIT_RESULT_F.md)
The audit recounted the table and agreed: 14 configurations, 6 failures at R1, median d1 −1.50 %, P2 holds, P1 fails.
It asked for:
- the sources to be stated as mixed and selected (caveats 1–2);
- the rounding and the single corner to be explicit (caveats 5–6);
- a negative median d1 not to be read as a measured speed-up.
All three are now in the text. The Q&A line no longer says the passing winners "were faster than claimed".

## Deviations
- **Zenodo outage (infrastructure, handled by the registered rule).**
  - At 03:05 ET Zenodo returned HTTP 503 for the EDA-env archive. Group ee013's job failed at the source fetch, before
    any flow ran. Run 41575196054 was cancelled at 03:12 ET, before the other six EDA-env groups could start.
  - The fetch script then gained a verified fallback: the authors' GitHub mirror at commit 89dfcbed, accepted only if
    all 1,295 files match a per-file sha256 manifest made from the pinned Zenodo archive. The mirror at that commit is
    byte-identical to the archive, and a tampered copy is rejected.
  - The workflow can now continue a chain from an earlier run's artifact.
  - The seven groups ran in r01b with the same tags.
  - No configuration, harness, judge, chain rule or test changed (F_LOG.md).
- **Deferred before registration (not a deviation):** ibex/sky130hd, for runtime (PREREG).

## Caveats
1. **Two sources, one dominant.** Eleven winners come from one agent (Kimi-k3) on one benchmark (EDA-env), with four
   aes tasks. Three come from one tuner database (ORFS-agent's). Not independent samples.
2. **The ORFS-agent rows are the database's best runs, not the paper's reported winners.** The paper never publishes its
   winning knob values. These rows' ECPs lie inside (aes) or 0.2 % above (ibex) the range the paper reports.
3. **Old flow, new flow.** ORFS-agent's harness runs ORFS ce8d36a7 (2024), where ABC is given the clock. EDA-env runs
   fb65d5b48 (2026). Neither is E5's image, and these numbers are not pooled with E5's.
4. **Same settings means the same absolute knobs.** EDA-env submissions set SETUP_SLACK_MARGIN and
   ABC_CLOCK_PERIOD_IN_PS in absolute ps; the rebuild keeps them. A rebuild that scaled them with the clock would ask
   a different question.
5. **Rounding and the small misses.** Each rebuild clock is the claim rounded up to the grid.
   - That gives every rebuild some headroom: 0.05–4.3 ps on ASAP7 and 0.049 ns for aes/sky130hd. Per config, R1 − C0:
     ee001 3.5, ee008 4.3, ee011 1.3, ee013 0.8, ee016 1.1, ee037 3.5, ee054 0.05, ee074 3.5, ee075 2.3, ee087 2.3,
     ee097 2.3, oa-aes-a7 2.3, oa-ibex-a7 0.8 ps.
   - The rounding favours passing, as in E5.
   - EDA-env 016 and 074 missed by 1.3 and 0.6 ps at 510 and 405 ps, inside one grid step. Under the registered judge
     they are failures.
6. **Predictive PDK, one corner.** ASAP7 is predictive and judged at its fast corner; sky130hd at tt only. Not
   signoff.

## Files
- docs/qa_week/F_PREREG.md, F_RESULT.md (this file), F_LOG.md.
- farm/qa/F/: configs.json, run_f.py, flib.py, orfsagent_run.sh, edaenv_run.py, fetch_sources.sh,
  edaenv_manifest.sha256, f_score.py, f_report.py, f_score_primary.json, batches/.
- Local records: /home/claude/qa/F/results/ (per run: metrics JSON, measurement, reports, gzipped logs; chains/).
