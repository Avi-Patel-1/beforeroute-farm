# Workstream AD — T3 result: does a pushed 7 nm layout meet its corrected claim without a rebuild? (re-time judge)

**Verdict: PREDICTION HELD.** All **9 of 9** of E5's ASAP7 winners, re-timed in place at their corrected claim,
passed the registered judge (needed ≥ 8 of 9), and the aes S0 layout asked 265 ps meets **385 ps** (WS +1.06 ps).
Scored 2026-11-03 10:39 UTC by `python3 farm/qa/AD/ad.py analyze` (committed; ad.py fbed433, adlib.py 286e4aa);
numbers in farm/qa/AD/ad_analyze_t3.json. Pre-registration: docs/qa_week/AD_PREREG.md with Amendment 1 (SHA-256
760b49c6…3869c, hash line 753295e, branch qa-ad-law). ASAP7 only, as registered (the 7 sky130 LibreLane winners were
not re-timed: their layouts were never kept).

## What was done (ASAP7 predictive 7 nm PDK, ORFS 202c7fccb, one FF corner, OpenRCX; units ps)
- **Replay:** each of E5's 9 winners (AutoTuner's top 3 per design) re-run with its exact setting and clock (runs
  `adr-*`, workflow run 41574461473). All 9 reproduced E5's worst setup and hold slack exactly (to 0.01 ps): same
  layout.
- **Corrected claim:** from the winner's own path groups at its asked clock T0: C\* = max(T0 − WS_reg-to-reg,
  T0 − WS_port/0.8), because I/O delays are 20% of the clock at every port, so a port path gains 0.8 ps of slack per ps
  of clock and a register path 1 ps. T\* = C\* rounded up to the 5 ps grid.
- **Re-time:** inside the finish step, after extraction, the run's own constraints are re-read with only the clock
  period changed, clocks propagated as ORFS does; nothing in the layout changes. Check: re-timing at T0 reproduced the
  flow's own slacks in all 9. **Judge at T\*:** setup WS ≥ 0, hold WS ≥ 0, detailed-route DRC 0.

| layout (E5 winner) | asked T0 | E5 claim | T\* | WS at T\* | hold at T\* | pass | E5's rebuild at its claim | area: layout vs that rebuild |
|---|---|---|---|---|---|---|---|---|
| gcd S0 (e5g-gcd-001) | 215 | 326.4 | 355 | +0.58 | +41.9 | yes | 330: fail; 355: fail | 50.9 vs 46.1 µm² (+10%) |
| gcd S1 (e5g-gcd-005) | 250 | 333.7 | 355 | +0.34 | +42.9 | yes | 335: fail; 355: pass | 50.3 vs 45.9 (+10%) |
| gcd S0 (e5g-gcd-002) | 265 | 337.9 | 360 | +3.07 | +42.0 | yes | 340: fail; 350: fail | 49.7 vs 45.4 (+10%) |
| aes S0 (e5g-aes-003) | 380 | 382.5 | 385 | +2.54 | +35.5 | yes | 385: fail; 405: fail | 1424 vs 1394 (+2%) |
| aes S1 (e5g-aes-005) | 305 | 383.7 | 385 | +1.31 | +35.2 | yes | 385: fail; 395: fail | 1619 vs 1402 (+15%) |
| **aes S0 (e5g-aes-001)** | **265** | 383.9 | **385** | **+1.06** | +35.1 | **yes** | 385: fail; 405: fail | 1661 vs 1394 (+19%) |
| ibex S0 (e5g-ibex-003) | 900 | 913.7 | 915 | +1.33 | +35.3 | yes | 915: fail; 920: pass | 2497 vs 2473 (+1%) |
| ibex S2 (e5g-ibex-008) | 720 | 914.7 | 915 | +0.32 | +35.2 | yes | 915: pass | 2644 vs 2457 (+8%) |
| ibex S0 (e5g-ibex-002) | 765 | 925.1 | 930 | +4.90 | +34.9 | yes | 930: pass | 2642 vs 2457 (+8%) |

## What it means (as registered)
- Below F, a pushed layout already meets its corrected claim; re-timing the layout in hand is a free judge, and the
  rebuild is the lazier build. Concretely: the aes layout built at 265 ps runs at 385 ps, while E5's chain, rebuilding
  at 385 and 405 ps, never passed (it found nothing below 530).
- The price is area: every pushed layout is larger than the rebuild at its claim (aes S0: +19%; gcd: +10%; ibex:
  +1–8%). The claim is a fair statement about the layout that was built; it is a guess about the cheaper layout a
  rebuild makes.
- Why the numbers are small: for register-limited layouts the re-time is close to bookkeeping (register slack moves
  1:1 with the clock), so T3 mostly confirms the 0.8/1.0 split and that nothing else in the constraints moves; the
  margins at T\* are +0.3 to +4.9 ps.

## Caveats
1. One gcd layout's re-time (gcd S0 at 215 → 355 ps, +0.577 ps) was seen in the smoke test before registration and
   disclosed in the PREREG.
2. ASAP7 only, one FF corner, no margins; LibreLane/sky130 layouts were not re-timed.
3. Re-timing changes only the clock in the constraints; it does not re-run extraction or repair (nothing in the layout
   changes, so no extraction change is expected).
