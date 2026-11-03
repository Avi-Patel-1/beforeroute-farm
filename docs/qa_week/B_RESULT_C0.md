# Workstream B, arm C0 — result: the sky130 audit scored by the register-to-register claim (no runs)

**Final.** Analysis run 2026-11-03 02:26Z (`date -u`). No flow runs; landed records only.
- Pre-registration: docs/qa_week/B_PREREG.md, SHA-256 `e813410515604e6f2d2517f9abaac1e6308c6876c5c87cd630a13860c9578d8f`
  (farm/prereg_hashes.txt, commit cdadff9 on branch qa-b-frozen-io, pushed 02:23Z; the file itself is commit 9e3c24f).
- Script: farm/qa/B/c0.py → farm/qa/B/c0.json. Input: agents/analysis/fixedpoint/data.json (built Oct 29 from
  results/*/metrics.json; 1,511 sky130 runs with slacks; LibreLane 3.0.16, nine-corner STA after OpenRCX).
- **Not a blind test.** The plan's own pass had already produced these numbers before registration (disclosed in the
  prereg). C0 is a registered, scripted reproduction.

## Question
ORFS issue #4583 (open, Sep 29 2026) proposes scoring a run by `period − reg2reg worst slack` instead of WNS, because
"WNS measures the SDC, not the tool": the I/O budget scales with the clock, so port paths' slack is bookkeeping. If a
tuner scored runs that way, would one-run claims stop overclaiming tight targets?

## Method (as registered)
- Register claim of a run: C_r = T − (register-to-register worst setup slack over the nine corners), in ns.
- Per setting (one flow configuration, run at ≥ 2 clock targets; 139 settings): the register fixed point F_r is where
  C_r(T) = T, interpolated between the adjacent targets where the setting goes from missing to meeting its
  register-to-register timing (`crossing` of agents/analysis/fixedpoint/analyze.py, copied verbatim). Only settings with
  such a bracket enter: **55 settings, 302 runs** (17 designs).
- Claim error e_r = (C_r − F_r)/F_r at each run; binned by how tight the target was, T/F_r.
- **Registered test:** median e_r over the tight bin (T/F_r < 0.9) < −10% → PASS.

## Result: **PASS.** Tight-target register claims overclaim a median **15.2%** (n 104)

| bin (T / F_r) | n | median e_r | runs beyond −5% | range |
|---|---|---|---|---|
| tight (< 0.9) | **104** | **−15.15%** | **89 (86%)** | −50.4% to +2.9% |
| near (0.9–1.1) | 117 | −0.00% | 7 (6%) | −8.7% to +6.4% |
| loose (1.1–1.5) | 58 | +7.1% (+8.1% without the 3 non-finite runs) | 6 | −25.1% to +40.4% (finite) |
| very loose (> 1.5) | 23 | +2.7% (+5.6% without the 3 non-finite runs) | 3 | −1.4% to +46.5% (finite) |

- Worst: x1d-y_huff-004 (y_huff asked at 6.81 ns; register claim 9.83 ns; register fixed point 19.83 ns): −50.4%.
- The overclaim is spread over designs: tight medians per design from −8.3% (PPU, n 12) to −34.9% (chacha, n 7); 14 of
  16 designs with tight runs are beyond −9%.
- Beside (same threshold, the audit's own 60 settings whose all-path fixed point is bracketed): 48 bracket a register
  fixed point; tight median **−14.7%** (n 84, 70 beyond −5%, worst −43.3%) → also PASS. The all-path audit number on
  those 60 settings was −14.5% (n 111).
- Data quirk: 6 cic_decimator record runs report an infinite register-to-register slack (no register path reported),
  i.e. C_r = −∞. All sit at T/F_r > 1.3; they do not touch the tight bin. They pull the loose and very-loose medians
  down; the finite-only medians are given in the table.

## What it means
Removing the port paths from the *score* does not remove the error. A tuner that ranked runs by
`period − reg2reg worst slack` would still be told, by a run asked at a tight target, that the setting is a median
15% faster than it is: the register-to-register paths themselves were built harder at the tighter target. That is
the physics half of TrueClock's claim, measured with the I/O bookkeeping taken out of the metric.

What C0 does **not** settle: the I/O budget still scaled with the clock *during* these runs, and the budget steers how
hard the tools work on register paths too (the #4583 sweep: cutting asap7/gcd's budget 20% → 2% moved its reg2reg
period 334.7 → 318.8 ps). Arm C1 re-runs the audit with the budget held fixed in the SDC itself; C2a rebuilds the 48
tuned winners that way.

## Q&A line
> "I re-scored my audit by the metric the OpenROAD maintainers are proposing, period minus register-to-register slack,
> which takes the I/O budget out of the score. Tight-target runs still overclaim by a median 15 percent, 104 runs,
> 89 of them by more than 5. The register paths themselves move with the target."

Do not say: "the I/O budget plays no role" (C0 removes it from the score, not from the flow; C1 is the test of that);
"significant" (55 settings from 17 designs, runs within a setting are not independent).
