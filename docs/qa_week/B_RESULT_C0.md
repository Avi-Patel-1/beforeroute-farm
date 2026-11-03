# Workstream B, arm C0 — result: the sky130 audit scored by the register-to-register claim (no runs; retrospective)

**Final.** Analysis run 2026-11-03 02:26Z (`date -u`). No flow runs; landed records only.
- Pre-registration: docs/qa_week/B_PREREG.md, SHA-256 `e813410515604e6f2d2517f9abaac1e6308c6876c5c87cd630a13860c9578d8f`
  (farm/prereg_hashes.txt, commit cdadff9 on branch qa-b-frozen-io, pushed 02:23Z; the file itself is commit 9e3c24f).
- Script: farm/qa/B/c0.py → farm/qa/B/c0.json. Input: agents/analysis/fixedpoint/data.json (built Oct 29 from
  results/*/metrics.json; 1,511 sky130 runs with slacks; LibreLane 3.0.16, nine-corner STA after OpenRCX).
- **Not a blind test; retrospective scope.** The plan's own pass had already produced these numbers before
  registration (disclosed in the prereg). C0 is a registered, scripted reproduction on runs that were built with the
  I/O budget scaling with the target (20% of T): it changes the *score*, not the runs.
- Revised 2026-11-03 after Codex's independent audit (AUDIT_RESULT_B_C0.md): wording now states a relative *period*
  error against an interpolated register-only crossing (not a frequency uplift), the retrospective scope, and a
  finite-only sensitivity. No number changed.

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
- Claim error e_r = (C_r − F_r)/F_r at each run: a relative error in *period* (ns), negative when the one-run claim is
  shorter (more optimistic) than the crossing. F_r is an interpolated zero-slack estimate between two measured targets,
  not an independently built and proven clock. Binned by how tight the target was, T/F_r.
- **Registered test:** median e_r over the tight bin (T/F_r < 0.9) < −10% → PASS.

## Result: **PASS.** At tight targets the register claim sits a median **15.15% below** the register crossing (n 104)

| bin (T / F_r) | n | median e_r | runs beyond −5% | range |
|---|---|---|---|---|
| tight (< 0.9) | **104** | **−15.15%** | **89 (86%)** | −50.4% to +2.9% |
| near (0.9–1.1) | 117 | −0.00% | 7 (6%) | −8.7% to +6.4% |
| loose (1.1–1.5) | 58 | +7.1% (+8.1% without the 3 non-finite runs) | 6 | −25.1% to +40.4% (finite) |
| very loose (> 1.5) | 23 | +2.7% (+5.6% without the 3 non-finite runs) | 3 | −1.4% to +46.5% (finite) |

- Worst: x1d-y_huff-004 (y_huff asked at 6.81 ns; register claim 9.83 ns; register fixed point 19.83 ns): −50.4%.
- The overclaim is spread over designs: tight medians per design from −8.3% (PPU, n 12) to −34.9% (chacha, n 7); 14 of
  16 designs with tight runs are beyond −9%.
Per design (finite runs; pooled numbers above):

| design | bracketed settings | runs | tight runs | tight median e_r | tight beyond −5% |
|---|---|---|---|---|---|
| APU | 7 | 33 | 13 | -19.9% | 11 |
| PPU | 8 | 43 | 12 | -8.3% | 10 |
| blabla | 1 | 8 | 4 | -12.7% | 3 |
| bm64 | 3 | 15 | 6 | -9.9% | 4 |
| chacha | 2 | 10 | 7 | -34.9% | 5 |
| cic_decimator | 4 | 17 | 1 | -8.9% | 1 |
| clip16_native | 3 | 18 | 11 | -12.6% | 10 |
| clip16_stickyround | 1 | 6 | 0 | – | – |
| md5 | 6 | 31 | 9 | -20.2% | 7 |
| ocs_blitter | 5 | 24 | 7 | -9.7% | 6 |
| picorv32 | 3 | 19 | 4 | -22.2% | 4 |
| salsa20 | 1 | 8 | 6 | -26.6% | 6 |
| sha512 | 1 | 4 | 2 | -14.3% | 2 |
| usb_cdc_core | 1 | 7 | 3 | -21.6% | 3 |
| wbqspiflash | 4 | 22 | 6 | -26.9% | 4 |
| y_huff | 3 | 16 | 8 | -29.4% | 8 |
| zipdiv | 2 | 15 | 5 | -32.5% | 5 |

- Beside (same threshold, the audit's own 60 settings whose all-path fixed point is bracketed): 48 bracket a register
  fixed point; tight median **−14.7%** (n 84, 70 beyond −5%, worst −43.3%) → also PASS. The all-path audit number on
  those 60 settings was −14.5% (n 111).
- Non-finite cases: 6 cic_decimator record runs (x6d-cic_decimator-006, x6e-cic_decimator-006/-007/-008,
  x7k-cic_decimator-006/-008) report an infinite register-to-register slack (no register path reported), i.e.
  C_r = −∞. All sit at T/F_r > 1.3 (3 loose, 3 very loose); none touches the tight bin or any setting's bracket.
- **Finite-only sensitivity** (those 6 runs dropped): tight median −15.15% (n 104, 89 beyond −5%) — unchanged; near
  −0.00% (117); loose +8.05% (55); very loose +5.61% (20). The registered test is unaffected.

## What it means (and does not)
Removing the port paths from the *score* does not remove the error. A tuner that ranked runs by
`period − reg2reg worst slack` would still be told, by a run asked at a tight target, a register-limited period a
median 15.15% shorter than the register crossing interpolated from the same setting's runs (a period error; it is not a
measured 15% frequency gain, and period and frequency percentages are not symmetric). The error survives taking the
port paths out of the score. C0 alone does not attribute it to the tools' optimization or to physics, and it does not
generalize beyond these designs and this flow: the runs were built under a scaling I/O budget, which can steer the
register paths too.

What C0 does **not** settle: the I/O budget still scaled with the clock *during* these runs, and the budget steers how
hard the tools work on register paths too (the #4583 sweep: cutting asap7/gcd's budget 20% → 2% moved its reg2reg
period 334.7 → 318.8 ps). Arm C1 re-runs the audit with the budget held fixed in the SDC itself; C2a rebuilds the 48
tuned winners that way.

## Q&A line
> "I re-scored my existing audit by the metric the OpenROAD maintainers are proposing, period minus
> register-to-register slack, which takes the I/O budget out of the score. At tight targets the claimed period was
> still a median 15 percent shorter than the setting's own register crossing, 104 runs, 89 of them by more than 5
> percent. The register paths move with the target too."

Do not say: "the I/O budget plays no role" (C0 removes it from the score, not from the flow; C1 is the test of that);
"15% faster" or "15% frequency" (it is a period error against an interpolated crossing); "significant" (55 settings
from 17 designs, runs within a setting are not independent).
