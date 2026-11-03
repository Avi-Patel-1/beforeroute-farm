# Workstream AD — T1 result: does the law, fitted on E5's grid alone, predict E5's rebuilds? (a registered RETRODICTION)

**Verdict: FAIL** on both registered conditions: **10 of 16** pass/fail calls right (needed ≥ 13) and median claim
error **3.52%** (needed ≤ 3%).

**This is a retrodiction, not a prediction.** All 16 rebuild outcomes it scores were in the record (E5_RESULT.md,
Nov 2) before the procedure was written. What was fixed in advance is only the procedure: it was registered in
docs/qa_week/AD_PREREG.md (SHA-256 e5c71b21…aab30, commit 12672e7, hash line 26e2ed9 in farm/prereg_hashes.txt,
branch qa-ad-law of Avi-Patel-1/beforeroute-farm) and run once, afterwards, by `python3 farm/qa/AD/ad.py t1`
(output farm/qa/AD/ad_t1.json). Computed 2026-11-03 03:14 UTC. No farm time.

## What was tested (units: ps; ASAP7 7 nm predictive PDK, OpenROAD-flow-scripts, one fast corner; E5's record)
- **The law** (ideas/mechanism-law.md): for a setting that can meet clock F, a run asked T claims C with
  (C − F)/F = s·(T/F − 1); s = s⁻ when T < F (the run fails setup), s⁺ when T > F. A claim C = T − worst setup slack is
  what AutoTuner ranks by.
- **Fit on E5's 30 grid runs only** (3 designs × 3 settings × 3–4 clocks): F per setting from its grid runs alone (the
  interpolated crossing claim = target, E5's method; all 9 settings bracketed), then least-squares slopes through the
  origin: **s⁻ = 0.259** (16 runs below F), **s⁺ = 0.566** (14 above). (The plan's 0.20 / 0.65 were fitted on all 44
  E5 runs including the rebuilds.)
- **Forecast** each of E5's 16 rebuild runs at its actual clock R: Ĉ = F + s·(R − F); called pass iff R ≥ F.

## The 16 forecasts
| rebuild | setting | asked R | grid-only F | real claim C | forecast Ĉ | error | real | forecast | right? |
|---|---|---|---|---|---|---|---|---|---|
| e5k-gcd-1-1 | gcd S0 | 330 | 373.6 | 350.4 | 362.3 | 3.4% | fail | fail | yes |
| e5k-gcd-1-2 | gcd S0 | 355 | 373.6 | 356.1 | 368.7 | 3.6% | fail | fail | yes |
| e5k-gcd-2-1 | gcd S1 | 335 | 356.1 | 350.4 | 350.7 | 0.1% | fail | fail | yes |
| e5k-gcd-2-2 | gcd S1 | 355 | 356.1 | 353.6 | 355.8 | 0.6% | **pass** | fail | no (F 1 ps above R) |
| e5k-gcd-3-1 | gcd S0 | 340 | 373.6 | 349.9 | 364.9 | 4.3% | fail | fail | yes |
| e5k-gcd-3-2 | gcd S0 | 350 | 373.6 | 353.1 | 367.5 | 4.1% | fail | fail | yes |
| e5k-aes-1-1 | aes S0 | 385 | 386.7 | 400.2 | 386.2 | 3.5% | fail | fail | yes |
| e5k-aes-1-2 | aes S0 | 405 | 386.7 | 407.4 | 397.0 | 2.5% | fail | pass | no |
| e5k-aes-2-1 | aes S1 | 385 | 429.7 | 390.3 | 418.1 | 7.1% | fail | fail | yes |
| e5k-aes-2-2 | aes S1 | 395 | 429.7 | 407.4 | 420.7 | 3.3% | fail | fail | yes |
| e5k-aes-3-1 | aes S0 | 385 | 386.7 | 400.2 | 386.2 | 3.5% | fail | fail | yes |
| e5k-aes-3-2 | aes S0 | 405 | 386.7 | 407.4 | 397.0 | 2.5% | fail | pass | no |
| e5k-ibex-1-1 | ibex S0 | 915 | 968.2 | 919.9 | 954.4 | 3.8% | fail | fail | yes |
| e5k-ibex-1-2 | ibex S0 | 920 | 968.2 | 909.9 | 955.7 | 5.0% | **pass** | fail | no |
| e5k-ibex-2-1 | ibex S2 | 915 | 1094.8 | 914.1 | 1048.2 | 14.7% | **pass** | fail | no |
| e5k-ibex-3-1 | ibex S0 | 930 | 968.2 | 925.2 | 958.3 | 3.6% | **pass** | fail | no |

Beside (no criterion): the claim itself as the forecast (each rebuild's claim = its winner's claim; every rebuild at or
above it called a pass, which is what the claim asserts): **4 of 16** calls right, median error **4.36%**. Calling every
rebuild a failure: 12 of 16 right.

## Why it failed
- **The fixed point from a 3–4-point grid is too coarse.** The miss → meet brackets of the grid are wide (ibex S0
  900 → 1260 ps, ibex S2 1080 → 1305 ps, aes S0 380 → 530 ps). Interpolating across them put ibex's F at 968 and
  1095 ps; the rebuilds show ibex S0 and S2 meet 920 and 915 ps (E5's grid-plus-rebuild F: 917 and 914). All four
  ibex passes were called failures, and the 14.7% error is ibex S2, whose grid F is 20% too slow.
- **The flow is not monotonic near F.** aes S0 missed at 380 (−2.5 ps), 385 (−15.2) and 405 (−2.4) but its grid F
  (386.7) says 405 passes; gcd S1 passed at 355 ps with F estimated at 356.1. A smooth law cannot call a 2 ps miss.
- **Direction holds; magnitude and the call do not.** The law beats the claim itself (10 vs 4 calls right; 3.5% vs
  4.4% error), but loses to "every rebuild fails" (12 of 16) — at 7 nm E5's rebuilds mostly fail, which is the
  record's finding, not the law's.

## What this means (as registered)
Two constants fitted on 9 settings' grids do not carry to the rebuilds within the registered tolerances: the law is a
median description of how claims move, and with F known only to a grid bracket it cannot replace the rebuild as a
judge. Say it as: "fitted on the grid alone, the slope law forecast E5's rebuild claims to a median 3.5% and called 10
of 16 pass/fail outcomes right; that is better than trusting the claim (4 of 16) but it failed my registered bar, so
the rebuild stays the judge." Do not call this a prediction: every outcome was known.

## Files
docs/qa_week/AD_PREREG.md (T1 section), farm/qa/AD/ad.py (`t1`), farm/qa/AD/ad_t1.json (all numbers),
farm/qa/E5/e5_analysis.json (the E5 record it reads).
