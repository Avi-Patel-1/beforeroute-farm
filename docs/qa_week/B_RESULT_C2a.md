# Workstream B, arm C2a — result: the 48 tuned winners with frozen I/O budgets, rebuilt at their claims (sky130)

**Final: all three tests final.** All 48 first rebuilds landed 2026-11-03 08:31Z; the last chain (the Bayesian md5
winner, continued by the workflow's resume stage) completed 11:06Z, so all 48 chains are complete (final scoring
11:10Z). md5's chain kept 18.45 ns (gain 1.005); aes_cipher's reached 13.45 ns (1.115); ocs_blitter's ended at
10.95 ns (1.000); picorv32's kept 9.85 ns (1.041), the clock its stock-budget rebuild had failed at. Two complete
chains, y_huff and bm64, never passed a rebuild and have no defined gain; as registered they are outside the gain's
population (chains with a passing rebuild), and they are counted as failures under C2a-i/ii instead. Scored with
farm/qa/B/c2a.py --final (fail-closed judge, commit 805c5b0 and later) → farm/qa/B/c2a.json; table by
farm/qa/B/c2a_table.py.
- Pre-registration: docs/qa_week/B_PREREG.md, SHA-256 e8134105…8d8f (commit 9e3c24f; hash line cdadff9, 02:23Z) and,
  with Amendment B.1, 3c633b31…74b7 (commit 55429f5; hash line 9c69316, 02:41Z), both before the first C2a run.
- Workflow run 41567699017 (branch qa-b-frozen-io, code commit c4f055f; 02:41Z–11:06Z, success): 18 stage-1 jobs,
  one resume stage of 4 jobs (aes_cipher, md5, ocs_blitter, picorv32 chains), third stage empty (skipped).
  201 flows, 23.9 flow-hours. LibreLane 3.0.16 / sky130A, the farm's pinned image; one flow per 4-vCPU runner.
- Judge (nine corners: min/nom/max RC × tt 25 °C 1.80 V, ss 100 °C 1.60 V, ff −40 °C 1.95 V, OpenRCX): setup and hold
  slack ≥ 0 at every corner, router DRC 0, slew/cap violation pins ≤ the design's stock reference; fail-closed
  admission (a run without a completed job record or any judged metric fails). Re-judging every chain entry from its
  own run directory changed 0 of the runner's verdicts, and replaying the registered chain rule over the re-judged
  entries reproduces every target the runner chose (0 trajectory differences; audit request). Final pass over all 201
  entries of the 48 complete chains, including the 4 continued by the resume stage: 0 and 0. This shows the recorded
  schedule is the one the rule prescribes; it says nothing about rebuilds that were never run.

## Question
In the record, 3 of the 8 Bayesian-tuned winners failed setup when rebuilt at their claimed clock, and rebuilding the
winners again at each new claim gained a median 1.10×. LibreLane budgets input and output delays as 20% of the target,
so part of every claim is bookkeeping. Hold the I/O delay fixed at D = 0.2 × each design's fastest closed clock
(F_best; XTEA 0.84 ns, bm64 2.28 ns), replay each winner at its own search target, rebuild it at the new claim: do
winners still fail, and does rebuilding again still pay?

## Bottom line
| test | prediction (plan, verbatim) | outcome | verdict |
|---|---|---|---|
| C2a-i | ≥2 of the 3 original failures still fail | bm64 and y_huff fail; picorv32 now passes | **PASS** (registered judge) |
| C2a-ii | ≥2 of 48 fail | 3 of 48 first rebuilds fail (bm64, y_huff, one cic_decimator winner) | **PASS** |
| C2a-iii | rebuild-again median ≥ 1.05× | median **1.0885** over the 46 chains with a passing rebuild (35 of 46 ≥ 1.02) | **PASS** |

**Read this with the failure reasons.** Of the 3 failing first rebuilds, 2 miss *setup* on register-to-register paths
(bm64 at 13.20 ns by −0.44 ns, then −0.50 at 13.65; cic_decimator's f1 winner at 4.30 ns by −0.010 ns, passing at
4.35) — the physics the plan predicted. The third, **y_huff, passes setup (+0.27 ns) and fails hold**: about 1,000
input-to-register endpoints violate hold by up to −0.48 ns at the slow (ss 100 °C) corner; register-to-register hold is
clean. Its fixed input delay (1.40 ns) is smaller than the stock 20% (2.2 ns at that clock), so input paths lose hold
margin. That is a consequence of the interface budget, not of the setup claim. **With a setup-only judge (beside, not
registered) C2a-i would be 1 of 3 (FAIL) and C2a-ii 2 of 48 (PASS).**

## What changed and what did not
- **First-rebuild verdicts barely moved: 47 of 48 match the record's.** The one change is picorv32, an original
  failure that now passes: its frozen replay claimed 10.24 ns (stock record 9.85) and the rebuild at 10.25 ns passed.
- **Claims moved a lot where ports limit.** At the same search target, frozen vs stock claim: median 0.0%, range −29.8%
  to +10.9%. XTEA (port-limited at loose targets): 7 of 8 winners claim 4.4–5.2 ns against 5.9–6.7 ns stock (the
  eighth, register-limited, is unchanged at 6.52); aes_cipher 14.98 vs 17.98 ns. Register-limited designs moved
  little in the median (zipdiv, cic_decimator, usb_cdc_core, wbqspiflash: +0.1% to +0.7%; single winners −8.3% to
  +6.4%).
- **Rebuilding again still pays, less where the gain was bookkeeping.** Race winners (40): median gain 1.105 frozen vs
  1.124 in the record (33 vs 34 of 40 ≥ 1.02). By design, frozen vs record: XTEA 1.12 vs 1.39, zipdiv 1.21 vs 1.19,
  usb_cdc_core 1.10 vs 1.10, wbqspiflash 1.08 vs 1.05, cic_decimator 1.03 vs 1.03. (The record's chains used Addendum
  35's closure rule with up to two refinements; C2a uses E5's single step back, so this comparison is approximate.)
- **The "law" mostly holds:** the first rebuild failed for 2 of the 4 winners whose frozen replay had negative setup
  slack (bm64, y_huff; md5 and usb_cdc_core b2 passed) and for 1 of the 44 with non-negative slack (cic f1): 45 of 48
  as the law says.

## Per design (counts beside the pooled numbers)
| design | winners | first rebuilds failing | why | median rebuild-again gain (finished chains) |
|---|---|---|---|---|
| aes_cipher, ocs_blitter | 1 each | 0 | – | 1.115, 1.000 |
| picorv32 | 1 | 0 | – | 1.041 |
| md5 | 1 | 0 | – | 1.005 |
| des, blabla | 1 each | 0 | – | 1.000 each |
| y_huff | 1 | 1 | hold (input-to-register, ss corner) | – |
| bm64 | 1 | 1 | setup, register-to-register | – |
| xtea | 8 | 0 | – | 1.125 (8) |
| cic_decimator | 8 | 1 | setup by 10 ps, register-to-register | 1.031 (8) |
| zipdiv | 8 | 0 | – | 1.209 (8) |
| usb_cdc_core | 8 | 0 | – | 1.100 (8) |
| wbqspiflash | 8 | 0 | – | 1.084 (8) |

## All 48 winners (paired with their record search run; frozen replay → first rebuild → chain)
D per design: plan.json `fbest` (B_PREREG.md table). "Record's first rebuild": A24d/A25d confirmation (Bayesian) or
Addendum 35's first closure run (race winners), under the stock budget.

| winner (search run) | design | T0 (ns) | claim, stock budget (record) | claim, frozen | first rebuild R1 | R1 verdict | R1 limiting path | record's first rebuild | kept clock K | T1/K |
|---|---|---|---|---|---|---|---|---|---|---|
| x1t-aes_cipher-017 | aes_cipher | 25.84 | 17.975 | 14.978 | 15.00 | pass | reg-to-reg | pass | 13.45 | 1.115 |
| x1t-picorv32-014 | picorv32 | 13.06 | 9.850 | 10.243 | 10.25 | pass | reg-to-reg | fail | 9.85 | 1.041 |
| x1t-y_huff-005 | y_huff | 10.97 | 10.240 | 11.353 | 11.40 | **fail** (hold -0.484) | port | fail | – | – |
| x2t-des-008 | des | 10.55 | 9.088 | 8.722 | 8.75 | pass | port | pass | 8.75 | 1.000 |
| x2t-md5-012 | md5 | 17.19 | 18.501 | 18.501 | 18.55 | pass | reg-to-reg | pass | 18.45 | 1.005 |
| x2t-bm64-007 | bm64 | 10.08 | 13.407 | 13.198 | 13.20 | **fail** (setup -0.439) | reg-to-reg | fail | – | – |
| x2t-ocs_blitter-022 | ocs_blitter | 11.23 | 11.050 | 10.947 | 10.95 | pass | reg-to-reg | pass | 10.95 | 1.000 |
| x2t-blabla-021 | blabla | 60.35 | 26.336 | 25.645 | 25.65 | pass | reg-to-reg | pass | 25.65 | 1.000 |
| xab1-xtea-005 | xtea | 11.90 | 6.515 | 6.515 | 6.55 | pass | reg-to-reg | pass | 4.85 | 1.351 |
| xaf1-xtea-004 | xtea | 11.71 | 6.213 | 4.709 | 4.75 | pass | port | pass | 4.20 | 1.131 |
| xag1-xtea-003 | xtea | 11.71 | 6.367 | 4.865 | 4.90 | pass | port | pass | 4.15 | 1.181 |
| xah1-xtea-007 | xtea | 11.71 | 6.008 | 4.507 | 4.55 | pass | port | pass | 4.10 | 1.110 |
| xab2-xtea-008 | xtea | 14.23 | 6.732 | 4.723 | 4.75 | pass | port | pass | 4.25 | 1.118 |
| xaf2-xtea-006 | xtea | 11.71 | 6.239 | 5.185 | 5.20 | pass | reg-to-reg | pass | 4.65 | 1.118 |
| xag2-xtea-004 | xtea | 11.71 | 5.927 | 4.427 | 4.45 | pass | reg-to-reg | pass | 4.10 | 1.085 |
| xah2-xtea-001 | xtea | 11.71 | 5.947 | 4.469 | 4.50 | pass | port | pass | 3.95 | 1.139 |
| xab1-cic_decimator-007 | cic_decimator | 4.97 | 4.831 | 4.722 | 4.75 | pass | reg-to-reg | pass | 4.75 | 1.000 |
| xaf1-cic_decimator-006 | cic_decimator | 4.50 | 4.240 | 4.299 | 4.30 | **fail** (setup -0.010) | reg-to-reg | fail | 4.35 | 1.000 |
| xag1-cic_decimator-006 | cic_decimator | 4.70 | 4.128 | 4.223 | 4.25 | pass | reg-to-reg | pass | 3.95 | 1.076 |
| xah1-cic_decimator-005 | cic_decimator | 4.50 | 3.952 | 3.995 | 4.00 | pass | reg-to-reg | pass | 4.00 | 1.000 |
| xab2-cic_decimator-005 | cic_decimator | 5.07 | 4.784 | 4.852 | 4.90 | pass | reg-to-reg | pass | 4.45 | 1.101 |
| xaf2-cic_decimator-007 | cic_decimator | 4.50 | 4.230 | 4.218 | 4.25 | pass | reg-to-reg | pass | 4.05 | 1.049 |
| xag2-cic_decimator-004 | cic_decimator | 4.60 | 4.095 | 4.107 | 4.15 | pass | port | pass | 3.95 | 1.051 |
| xah2-cic_decimator-008 | cic_decimator | 4.50 | 3.952 | 3.945 | 3.95 | pass | reg-to-reg | pass | 3.90 | 1.013 |
| xab1-zipdiv-008 | zipdiv | 11.70 | 7.535 | 7.306 | 7.35 | pass | reg-to-reg | pass | 6.15 | 1.195 |
| xaf1-zipdiv-005 | zipdiv | 8.59 | 7.183 | 7.641 | 7.65 | pass | reg-to-reg | pass | 5.85 | 1.308 |
| xag1-zipdiv-005 | zipdiv | 8.59 | 7.228 | 7.393 | 7.40 | pass | reg-to-reg | pass | 6.00 | 1.233 |
| xah1-zipdiv-005 | zipdiv | 8.59 | 6.675 | 6.680 | 6.70 | pass | reg-to-reg | pass | 5.70 | 1.175 |
| xab2-zipdiv-006 | zipdiv | 10.88 | 7.700 | 7.062 | 7.10 | pass | reg-to-reg | pass | 6.00 | 1.183 |
| xaf2-zipdiv-008 | zipdiv | 8.59 | 6.987 | 7.334 | 7.35 | pass | reg-to-reg | pass | 7.05 | 1.043 |
| xag2-zipdiv-004 | zipdiv | 8.59 | 7.224 | 7.235 | 7.25 | pass | reg-to-reg | pass | 5.90 | 1.229 |
| xah2-zipdiv-005 | zipdiv | 8.59 | 6.812 | 6.812 | 6.85 | pass | reg-to-reg | pass | 5.60 | 1.223 |
| xab1-usb_cdc_core-005 | usb_cdc_core | 7.36 | 6.644 | 6.655 | 6.70 | pass | reg-to-reg | pass | 5.70 | 1.175 |
| xaf1-usb_cdc_core-001 | usb_cdc_core | 7.02 | 6.341 | 6.357 | 6.40 | pass | port | pass | 5.70 | 1.123 |
| xag1-usb_cdc_core-007 | usb_cdc_core | 7.02 | 6.320 | 6.456 | 6.50 | pass | port | pass | 5.60 | 1.161 |
| xah1-usb_cdc_core-008 | usb_cdc_core | 7.02 | 6.187 | 6.211 | 6.25 | pass | port | pass | 5.80 | 1.078 |
| xab2-usb_cdc_core-005 | usb_cdc_core | 7.22 | 7.326 | 7.333 | 7.35 | pass | reg-to-reg | pass | 7.35 | 1.000 |
| xaf2-usb_cdc_core-004 | usb_cdc_core | 7.02 | 6.328 | 6.336 | 6.35 | pass | reg-to-reg | pass | 5.60 | 1.134 |
| xag2-usb_cdc_core-002 | usb_cdc_core | 7.02 | 6.327 | 6.109 | 6.15 | pass | port | pass | 6.15 | 1.000 |
| xah2-usb_cdc_core-002 | usb_cdc_core | 7.02 | 6.327 | 6.109 | 6.15 | pass | port | pass | 6.15 | 1.000 |
| xab1-wbqspiflash-006 | wbqspiflash | 10.29 | 8.541 | 8.446 | 8.45 | pass | reg-to-reg | pass | 6.85 | 1.234 |
| xaf1-wbqspiflash-007 | wbqspiflash | 8.49 | 7.942 | 7.961 | 8.00 | pass | reg-to-reg | pass | 6.45 | 1.240 |
| xag1-wbqspiflash-003 | wbqspiflash | 8.49 | 7.972 | 8.114 | 8.15 | pass | reg-to-reg | pass | 7.55 | 1.079 |
| xah1-wbqspiflash-003 | wbqspiflash | 8.49 | 7.957 | 7.983 | 8.00 | pass | reg-to-reg | pass | 7.60 | 1.053 |
| xab2-wbqspiflash-008 | wbqspiflash | 8.83 | 8.542 | 8.589 | 8.60 | pass | reg-to-reg | pass | 7.90 | 1.089 |
| xaf2-wbqspiflash-008 | wbqspiflash | 8.49 | 8.247 | 8.220 | 8.25 | pass | reg-to-reg | pass | 7.85 | 1.051 |
| xag2-wbqspiflash-008 | wbqspiflash | 8.49 | 7.980 | 7.980 | 8.00 | pass | reg-to-reg | pass | 7.70 | 1.039 |
| xah2-wbqspiflash-003 | wbqspiflash | 8.49 | 7.966 | 7.957 | 8.00 | pass | reg-to-reg | pass | 7.35 | 1.088 |

## Already seen, and foreseeable (by logical configuration)
- The xah1-xtea-007 chain (b2a-xtea-04) repeats the smoke chain exactly (replay at 11.71 ns, rebuilds at 4.55, 4.15,
  4.10 ns): identical outcomes, seen before launch. Without it the race median gain is 1.101 instead of 1.105 (32 of
  39 ≥ 1.02) and C2a-iii's median is 1.0884 (n 45) instead of 1.0885, still PASS; no first-rebuild failure involved
  (it passed).
- Controls: the sky130 control smoke (XTEA at F_best, IO_DELAY_CONSTRAINT 20) was identical to the record in all 281
  metrics. All 201 C2a run directories carry the frozen delay D both in the resolved config
  (CLOCK_PERIOD × IO_DELAY_CONSTRAINT / 100) and in base.sdc's own "Setting input/output delay" log lines (201 of 201
  within 1e-6 ns).

## Status counts (fail-closed judge)
Replays W: 44 completed and passing at their own target, 3 completed with setup failures, 1 with setup and hold
failures (y_huff); first rebuilds: 45 pass, 2 setup failures, 1 hold failure. All 201 chain runs have a completed job
record; no flow errors, no retries needed, no runs missing, no run excluded by admission.

## What it means
Freezing the I/O budget moves the claims of port-limited winners (XTEA by a quarter) but not whether a winner survives
a rebuild at its claim: 47 of 48 first-rebuild verdicts are the record's. The failures that remain are register-path
physics (bm64, cic_decimator) and one interface-hold failure created by the smaller fixed input delay (y_huff).
Rebuilding again still gains a median 1.09× over all 46 chains with a passing rebuild (1.105× over the 40 race
winners, record 1.124×), and the designs whose gains were mostly register physics keep them; XTEA's large record gains
(1.39×) shrink to 1.12× once its I/O budget stops sliding with the target.

## Q&A lines
> "I froze the I/O budgets and rebuilt all 48 tuned winners at their new claims. 47 of 48 came out exactly as before:
> the ones that failed still fail, except one. The surviving failures are register-to-register paths, and one is a
> hold failure on the inputs, which a fixed input budget makes harder. Rebuilding again still gains about 9 percent
> in the median."

Do not say: "all three original failures still fail" (picorv32 now passes); "physics" for y_huff (it fails hold on
input paths); "significant" (48 winners from 13 designs, 40 of them from 5).

## Caveats
1. D is a retrospective, per-design choice (0.2 × the fastest clock closed in the record), an experimental external
   budget, not a production product budget; y_huff's F_best (7.01 ns) is far below its other passing runs, which makes
   its D small. Arm S (D = 1.0 ns flat for the race designs) bounds the choice; it has not run yet.
2. The winners were selected by searches run under the stock budget; only C2b repeats the search with frozen budgets.
3. Chain rule differs from the record's (one step back vs up to two refinements).
4. C2a-i passes on the registered judge (setup, hold, DRC, slew/cap at nine corners) only because y_huff fails hold on
   input paths; on setup alone it would be 1 of 3. Quote it with the reasons.
