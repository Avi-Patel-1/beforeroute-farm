# Workstream B, arm C3 — result: the 7 nm audit with the I/O budget frozen (ASAP7, OpenROAD-flow-scripts)

**Final.** All 46 runs landed 2026-11-03 06:56Z (`date -u`); scored with farm/qa/B3/c3.py (branch qa-b-asap7) →
farm/qa/B3/c3.json. Nothing is still running for C3.
- Pre-registration: docs/qa_week/B_PREREG.md on branch qa-b-frozen-io; SHA-256 e8134105…8d8f (original, commit
  9e3c24f, hash line cdadff9, 02:23Z) and 3c633b31…74b7 (with Amendment B.1, commit 55429f5, hash line 9c69316,
  02:41Z), both in farm/prereg_hashes.txt before this arm's first non-smoke run (02:42Z).
- Workflow run 41567743736 (branch qa-b-asap7, code commit 5def9c4; the runner picked the top 3 and ran the chains).
  Smoke (not part of this result): run 41566736833.
- Image: ORFS 202c7fccb (`openroad/orfs@sha256:cba40c1d…`), as E5. One flow per 4-vCPU GitHub runner.
- Judge: E5's (e5lib, unchanged): flow completed; setup and hold slack ≥ 0 at ORFS's **single** ASAP7 corner (FF
  libraries, 0.77 V, 25 °C; one RC corner, no margins); detailed-route DRC 0. This is a one-corner gate on a predictive
  PDK, **not** a nine-corner signoff (the sky130 arms use nine corners).

## Question
E5 found that all six of AutoTuner's top picks on gcd and aes failed when rebuilt at their claimed clock, and that
ibex's claims held within 0.7%. E5's own split: gcd's misses were I/O bookkeeping (the output budget was 20% of the
target), aes's were register-to-register physics. C3 reruns E5's grid with the I/O delay held fixed at 0.2 × P0, the
budget at each design's own ORFS clock (gcd 62 ps, aes 76 ps, ibex 180 ps), and asks whether the picks still fail.

## Method (as registered)
- E5's 30-run grid unchanged (per design: S0 as shipped at 0.70/0.85/1.00/1.40 × P0; S1 sparser floorplan and S2
  denser placement at 0.80/1.20/1.45 × P0). One change: after AutoTuner's `set clk_period` substitution,
  `set clk_io_pct 0.2` → `0.2·P0/T` (8 significant digits); at T = P0 the SDC is E5's, byte for byte.
- Claim C = asked period − post-route worst setup slack (AutoTuner's `effective_clk_period`). Picks = top 3 per design
  by AutoTuner's `calculate_score`, chosen on the runner from the 10 frozen runs. Chain = E5's rule (rebuild at the claim
  rounded up to 5 ps; keep rebuilding while it passes; one step back on a miss; ≤ 4 rebuilds), every rebuild frozen.
  K = kept clock (smallest passing clock); d1 = C1/C0 − 1 (first rebuild's claim vs the pick's claim).
- Registered tests: **C3-gcd** each of gcd's 3 picks has |K/C0 − 1| ≤ 2%, or a register-limited first rebuild;
  **C3-aes** ≥ 2 of aes's 3 picks fail their first rebuild; **C3-ibex** each of ibex's 3 picks has |K/C0 − 1| ≤ 1%.

## Bottom line
| test | prediction (plan, verbatim) | outcome | verdict |
|---|---|---|---|
| C3-gcd | gcd's picks hold within 2% or turn register-limited | K/C0 = 1.018, 1.002, 1.011 (all three still port-limited) | **PASS** |
| C3-aes | aes ≥2 of 3 still fail | 3 of 3 first rebuilds fail; no chain reached a passing clock up to 395 ps | **PASS** |
| C3-ibex | ibex within 1% | 1.0015, 1.0006, **1.015** (the third pick kept a clock 1.5% slower than claimed) | **FAIL** |

- **gcd: the I/O bookkeeping was the miss.** With the output budget held at 62 ps, gcd's claims stopped falling with the
  target (346.2, 349.4, 343.7 ps when asked 215, 265, 310 ps, against E5's 326.4, 337.9, 343.7), and every pick kept a
  clock within 1.8% of its claim. One first rebuild still missed (pick 1: 345 ps, −5.6 ps on the output path); it
  passed one step back.
- **aes: physics.** All three picks are register-to-register limited, all three first rebuilds failed (380 ps
  −2.5 ps; 385 ps −5.3 ps; 385 ps −2.6 ps), and every step-back failed too (385, 395, 390 ps). Holding the I/O budget
  changed nothing about that.
- **ibex: mostly held, one pick did not.** Picks 1–2 passed at their claim (915 and 920 ps; E5's stock rebuild at
  915 ps had missed by 4.9 ps). Pick 3, asked at 630 ps (0.70 × P0), claimed 936.0 ps, failed at 940 ps (its rebuild
  claimed 950.3 ps) and kept 950 ps: 1.5%, over the registered 1%.
- **Controls:** the three runs at T = P0 (b3g-gcd/aes/ibex-003) are identical to E5's e5g-*-003 in every metric except
  execution-time keys (470, 475 and 489 keys). **Loaded constraints:** in all 46 runs, the finish report's output/input
  external delays are exactly −0.2·P0 (−62/−76/−180 ps) and the SDC's `clk_period × clk_io_pct` = 0.2·P0; every run
  loaded the same five FF liberty files. All 46 runs completed (24 setup failures, 22 passes; no hold, DRC or flow
  failures).

## The nine picks
| chain | pick (setting, asked T0) | claim C0 | first rebuild R1 | R1 result (slack, limiting path) | C1 | d1 | chain after R1 | kept K | K/C0 |
|---|---|---|---|---|---|---|---|---|---|
| b3k-gcd-1 | b3g-gcd-003 (S0, 310 = P0) | 343.7 | 345 | fail (−5.6 ps, port) | 350.6 | +2.0% | 355 pass → 350 pass | 350 | 1.018 |
| b3k-gcd-2 | b3g-gcd-005 (S1, 250) | 344.2 | 345 | pass (+0.5 ps, port) | 344.5 | +0.1% | converged | 345 | 1.002 |
| b3k-gcd-3 | b3g-gcd-001 (S0, 215) | 346.2 | 350 | pass (+4.8 ps, port) | 345.2 | −0.3% | converged | 350 | 1.011 |
| b3k-aes-1 | b3g-aes-001 (S0, 265) | 376.9 | 380 | fail (−2.5 ps, reg) | 382.5 | +1.5% | 385 fail (−2.6) | none | – |
| b3k-aes-2 | b3g-aes-005 (S1, 305) | 381.5 | 385 | fail (−5.3 ps, reg) | 390.3 | +2.3% | 395 fail (−3.7) | none | – |
| b3k-aes-3 | b3g-aes-003 (S0, 380 = P0) | 382.5 | 385 | fail (−2.6 ps, reg) | 387.6 | +1.4% | 390 fail (−5.1) | none | – |
| b3k-ibex-1 | b3g-ibex-003 (S0, 900 = P0) | 913.7 | 915 | pass (+0.8 ps, reg) | 914.2 | +0.1% | converged | 915 | 1.0015 |
| b3k-ibex-2 | b3g-ibex-008 (S2, 720) | 919.5 | 920 | pass (+2.9 ps, reg) | 917.1 | −0.3% | converged | 920 | 1.0006 |
| b3k-ibex-3 | b3g-ibex-001 (S0, 630) | 936.0 | 940 | fail (−10.3 ps, reg) | 950.3 | +1.5% | 955 pass → 950 pass | 950 | 1.015 |

E5 (stock budget, same grid) for comparison: picks gcd 001/005/002 (claims 326.4/333.7/337.9; all first rebuilds
failed, one chain kept 355), aes 003/005/001 (382.5/383.7/383.9; all failed, none kept), ibex 003/008/002
(913.7/914.7/925.1; kept 920/915/930). Freezing the budget changed which runs AutoTuner ranks first on gcd and ibex
(it raised the claims at tight targets), so the picks are not the same runs. The causal contrast for the budget is
the paired grid table below (same setting, same target, only the I/O delay changed); pick-to-pick comparisons mix the
budget change with a different selection. Unique settings among the picks: 2 per design (S0 twice at different
targets, plus S1 on gcd and aes and S2 on ibex); the S0 picks at P0 (gcd-003, aes-003, ibex-003) are the stock-identical
control configurations, and aes picks 1 and 3 share their S0 rebuild at 385 ps (identical results). For aes, "no kept clock" means no rebuild in the chain passed at ≤ 395 ps;
it is not the setting's attainable clock (aes settings pass at the grid's 455–550 ps targets).

## Every grid run, frozen vs E5's stock budget (paired by grid position)
| run (frozen ↔ stock) | setting | T (ps) | I/O delay frozen / stock (ps) | claim frozen | claim stock | change | limiting path | pass |
|---|---|---|---|---|---|---|---|---|
| gcd-001 | S0 | 215 | 62 / 43 | 346.2 | 326.4 | +6.1% | port / port | fail / fail |
| gcd-002 | S0 | 265 | 62 / 53 | 349.4 | 337.9 | +3.4% | port / port | fail / fail |
| gcd-003 | S0 | 310 | 62 / 62 | 343.7 | 343.7 | 0 (control) | port / port | fail / fail |
| gcd-004 | S0 | 435 | 62 / 87 | 374.8 | 402.4 | −6.9% | port / port | pass / pass |
| gcd-005 | S1 | 250 | 62 / 50 | 344.2 | 333.7 | +3.2% | port / port | fail / fail |
| gcd-006 | S1 | 370 | 62 / 74 | 363.4 | 359.1 | +1.2% | port / port | pass / pass |
| gcd-007 | S1 | 450 | 62 / 90 | 376.1 | 405.2 | −7.2% | port / port | pass / pass |
| gcd-008 | S2 | 250 | 62 / 50 | 352.2 | 338.5 | +4.0% | port / port | fail / fail |
| gcd-009 | S2 | 370 | 62 / 74 | 365.1 | 361.6 | +1.0% | port / port | pass / pass |
| gcd-010 | S2 | 450 | 62 / 90 | 374.6 | 401.5 | −6.7% | port / port | pass / pass |
| aes-001 | S0 | 265 | 76 / 53 | 376.9 | 383.9 | −1.8% | reg / reg | fail / fail |
| aes-002 | S0 | 325 | 76 / 65 | 387.1 | 389.1 | −0.5% | reg / reg | fail / fail |
| aes-003 | S0 | 380 | 76 / 76 | 382.5 | 382.5 | 0 (control) | reg / reg | fail / fail |
| aes-004 | S0 | 530 | 76 / 106 | 473.6 | 477.2 | −0.8% | reg / reg | pass / pass |
| aes-005 | S1 | 305 | 76 / 61 | 381.5 | 383.7 | −0.6% | reg / reg | fail / fail |
| aes-006 | S1 | 455 | 76 / 91 | 441.0 | 439.1 | +0.4% | reg / reg | pass / pass |
| aes-007 | S1 | 550 | 76 / 110 | 485.2 | 487.9 | −0.5% | reg / reg | pass / pass |
| aes-008 | S2 | 305 | 76 / 61 | 394.8 | 405.7 | −2.7% | reg / reg | fail / fail |
| aes-009 | S2 | 455 | 76 / 91 | 442.0 | 443.6 | −0.4% | reg / reg | pass / pass |
| aes-010 | S2 | 550 | 76 / 110 | 474.6 | 481.1 | −1.3% | reg / reg | pass / pass |
| ibex-001 | S0 | 630 | 180 / 126 | 936.0 | 936.3 | −0.0% | reg / reg | fail / fail |
| ibex-002 | S0 | 765 | 180 / 153 | 936.4 | 925.1 | +1.2% | reg / reg | fail / fail |
| ibex-003 | S0 | 900 | 180 / 180 | 913.7 | 913.7 | 0 (control) | reg / reg | fail / fail |
| ibex-004 | S0 | 1260 | 180 / 252 | 1236.3 | 1201.5 | +2.9% | reg / reg | pass / pass |
| ibex-005 | S1 | 720 | 180 / 144 | 943.5 | 946.8 | −0.3% | reg / reg | fail / fail |
| ibex-006 | S1 | 1080 | 180 / 216 | 1072.8 | 1065.9 | +0.6% | reg / reg | pass / pass |
| ibex-007 | S1 | 1305 | 180 / 261 | 1232.7 | 1192.0 | +3.4% | reg / reg | pass / pass |
| ibex-008 | S2 | 720 | 180 / 144 | 919.5 | 914.7 | +0.5% | reg / reg | fail / fail |
| ibex-009 | S2 | 1080 | 180 / 216 | 1085.0 | 1085.0 | +0.0% | reg / reg | fail / fail |
| ibex-010 | S2 | 1305 | 180 / 261 | 1220.3 | 1234.6 | −1.2% | reg / reg | pass / pass |

Pass/fail is the same as E5 at all 30 grid points. Per design, the change in claim: gcd's port-limited claims move by
−7.2% to +6.1% (they now barely depend on the target below P0); aes and ibex, register-limited, move by −2.7% to +3.4%
even though the I/O budget cannot enter their limiting paths directly.

## Beside (descriptive, no criterion): claim error against each setting's own crossing, frozen budgets
F per setting = the interpolated crossing of C(T) = T (agents/analysis/fixedpoint `crossing`, as E5's S1/S2), grid and
chain runs pooled; e = (C − F)/F (a period error):
| bin (T/F) | frozen, n | median e | E5 stock (same method), n | median e |
|---|---|---|---|---|
| tight (< 0.9) | 13 | −1.1% | 13 | −5.6% |
| near (0.9–1.1) | 22 | −0.0% | 23 | −0.7% |
| loose (1.1–1.5) | 11 | +15.3% | 10 | +15.2% |
At 7 nm the tight-target overclaim mostly goes away with the budget held (it was gcd's output path); the loose-target
underclaim (+15%) does not move: the flow relaxes register paths when given slack, whatever the I/O budget.

## Already-seen and foreseeable configurations (audit request: by logical configuration)
- b3g-gcd-001 (gcd S0 at 215 ps, frozen) and b3g-gcd-003 (gcd at P0) repeat smoke runs smoke-b3g-gcd-001/003 exactly;
  their outcomes were known before launch. Without them, gcd's picks would differ (gcd-003 is pick 1, gcd-001 pick 3);
  the verdicts cannot be recomputed without them because AutoTuner's selection is over all 10 grid runs.
- Identical configurations inside the arm gave identical results: b3k-aes-1-1 (S0 at 380, frozen = stock config)
  = the grid control b3g-aes-003 = E5's e5g-aes-003 (−2.463 ps); b3k-aes-1-2 = b3k-aes-3-1 (S0 at 385);
  b3k-gcd-1-3 = b3k-gcd-3-1 (S0 at 350).

## What it means
On 7 nm the two mechanisms TrueClock names separate cleanly. Where a port path limits the design (gcd), the 20% I/O
budget sliding with the target was the whole miss: hold the budget and AutoTuner's picks keep a clock within 2% of what
they claimed. Where register-to-register paths limit it (aes), the picks still fail when rebuilt at their claim, and
the budget is irrelevant. ibex, also register-limited, mostly held, but one of three picks, asked at 0.70× its default
clock, missed by 1.5%, so "ibex within 1%" does not hold with frozen budgets.

## Q&A lines
> "I held the I/O delays fixed and reran the 7-nanometer audit. On gcd, which is limited by an output path, the miss
> disappeared: AutoTuner's picks held to within 2 percent. On AES, limited by register-to-register paths, all three
> picks still failed at their claimed clock. So at 7 nm one design's failure was bookkeeping and the other's was real."

If asked about Ibex: *"Two of the three picks held to within 0.15 percent; the third, asked at 70 percent of its
default clock, missed by 1.5 percent, which is outside the 1 percent I had registered."*

Do not say: "nine-corner signoff" for ASAP7 (one FF corner); "the I/O budget explains the 7 nm results" (it explains
gcd's, not aes's); "significant" (3 designs, 9 picks); anything implying AES has no passing clock (its settings pass at
the grid's looser targets, 455–550 ps).

## Caveats
1. ASAP7 is a predictive PDK judged at one fast corner with no margins; absolute clocks are optimistic.
2. D on ASAP7 is 0.2 × P0 (ORFS's default clock), as the plan specified, not a record F_best as on sky130.
3. Selection under frozen budgets: the picks are not E5's picks on gcd and ibex, so pick-by-pick comparisons with E5 are
   between different runs.
4. The flow is deterministic but not smooth in its inputs: aes S0 at 385 ps missed by 15.2 ps with E5's stock budget
   (77 ps) and by 2.6 ps with the frozen one (76 ps).
5. 3 small designs, 9 picks (3 per design), 5 ps rebuild grid (1.1–2.3% of these clocks).
6. Codex's audit requests are folded in (status classes, loaded-constraint evidence, smoke overlap, per-design
   reporting, fail-closed admission; E5's judge already requires a completed status and setup/hold/DRC values).
