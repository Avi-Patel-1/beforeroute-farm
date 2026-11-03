# Workstream AD (TrueClock overnight push) — pre-registration: is "slack is not distance" a property of the flow? (experiment A: tests T1, T2, T3) and three nodes in one flow (experiment D)

Written 2026-11-03 (UTC; Nov 2 evening ET) by the AD agent of the TrueClock overnight push, after the slides were
locked (Oct 30) and **before any non-smoke run of this file** (tags `adb-*`, `ads-*`, `adsk-*`, `adg-*`, `adgk-*`,
`adr-*`, `adc-*`). Avi Patel (the project owner) is asleep and did not see this file, its design choices or any run
before launch; the predictions are not ours: they are copied verbatim from the plan Avi read (ideas/mechanism-law.md,
ideas/advanced-nodes.md, as quoted by the overnight coordinator). The file's SHA-256 is appended to
farm/prereg_hashes.txt on branch qa-ad-law and pushed before the first non-smoke batch is pushed. Results:
docs/qa_week/AD_RESULT_T1.md (T1) and docs/qa_week/AD_RESULT.md (T2, T3, D).
Code: branch qa-ad-law (from qa-e5-asap7), `farm/qa/AD/` (orfs_run.sh, run_group.py, adlib.py, ad_hook.tcl, ad.py,
grid.json) and `.github/workflows/ad_law.yml`; the commit that adds this file freezes it.

## Question
TrueClock's claimed clock C = asked period T − post-route worst setup slack, the number AutoTuner ranks settings by.
Against F, the clock a setting can actually meet, the record fits a two-sided "law" (ideas/mechanism-law.md §2;
fitted on data already seen, so it is the claim under test, not a result): with r = T/F and e = (C − F)/F,

  e = s⁻ (r − 1) for asks tighter than F (the run fails setup), e = s⁺ (r − 1) for looser asks (it passes);
  equivalently F = T − k·slack with k = 1/(1 − s): "slack is not distance".

Fitted constants: sky130/LibreLane (328 runs) s⁻ = 0.59, s⁺ = 0.29; ASAP7/ORFS (E5, 44 distinct runs) s⁻ = 0.20,
s⁺ = 0.65. The two flows differ in node *and* flow *and* in whether synthesis sees the clock (LibreLane's ABC gets the
clock as a delay target; in E5's ORFS it did not: gcd and aes use OpenROAD's `syn`, ibex Yosys/ABC with no target).
- **A** asks whether the constants belong to the flow: T1 (does the law fitted on E5's grid predict E5's rebuilds?),
  T2 (does ORFS on sky130hd behave like ORFS on ASAP7 — flow — or like LibreLane on sky130 — node? does telling ABC
  the clock steepen ORFS's tight-side slope — synthesis?), T3 (does a pushed layout, re-timed at its corrected
  claim, meet it without a rebuild?).
- **D** repeats E5's 7 nm protocol (grid, AutoTuner's top 3, rebuild chains) on sky130hd and GT2N (2 nm) in the same
  pinned ORFS image, so the node changes and the flow does not.

## Toolchain (frozen)
- Image `openroad/orfs@sha256:cba40c1de21f048b545c005210dabe728bf501f4bb7d5ae5f03b33feb52b49fa` (E5's image;
  ORFS commit 202c7fccb; Yosys 0.68+post). It ships the asap7, sky130hd and gt2n platforms and the designs used here
  (asap7 gcd/aes/ibex; sky130hd gcd/aes/ibex; gt2n gcd/aes; GT2N ships no ibex).
- GitHub Actions ubuntu-latest (4 vCPU), one flow at a time per job (gcd groups may run 2 at once), NUM_CORES=4 for
  every flow, a fresh container per flow (`farm/qa/AD/orfs_run.sh`). Workflow `ad_law.yml`, triggered by a push to
  qa-ad-law that changes farm/qa/AD/dispatch.json; at most 4 jobs at once (this workstream's farm share).
- Each run uses the design's own ORFS config.mk and constraint.sdc for its platform, unchanged; knob overrides on
  the make command line (as AutoTuner passes them); the clock target by AutoTuner's `write_sdc` substitution of
  `set clk_period` (in ns for sky130hd, ps for asap7 and gt2n). The flow runs to the finish report (route, extraction,
  post-route STA). The read-only finish hook (`ad_hook.tcl`; part 1 = E5's `e5_hook.tcl`) records worst setup slack
  per path group and worst hold slack.
- Corners and parasitics (ORFS's own per platform): ASAP7 BC (FF, 0.77 V, 25 °C), OpenRCX; sky130hd tt_025C_1v80,
  OpenRCX; gt2n TT 0.7 V 25 °C (the only corner GT2N ships), and post-route parasitics as the platform provides
  (see Smoke).

## Definitions (E5's, unchanged except where marked)
- **Claimed clock** C = T − `finish__timing__setup__ws` (AutoTuner's `effective_clk_period`). All times in ps
  (sky130hd metrics are in ns and are multiplied by 1000).
- **Tuner ranking:** AutoTuner's `calculate_score` (step 1), C·100 + (C/10)·DRC; runs without metrics never win;
  ties by tag. **Winners** = a design's top 3 among its 10 grid runs, picked on the runner (`adlib.top3`).
- **Judge (pass):** flow completed; finish setup WS ≥ 0 and hold WS ≥ 0 at the platform's ORFS corner; detailed-route
  DRC 0 (E5's ASAP7 judge, applied to all three platforms; no slew/cap condition, as in E5).
- **Rebuild chain:** E5's rule verbatim (`adlib.chain_next` = `e5lib.chain_next`): first rebuild at ceil5(C0); keep
  rebuilding at ceil5 of each passing claim; step back once after a failed first rebuild; ≤ 4 rebuilds; kept clock =
  smallest passing clock. **ceil5** = up to the 5 ps grid on every platform (E5's ASAP7 grid, kept for all three
  nodes of the one flow: under 0.5% of the sky130hd periods, about 1–4% of the GT2N periods).
- **Setting** = all non-clock knobs (incl. SYNTH_USE_SYN); a run = a setting at one clock.
- **F** per setting: E5's `crossing` (copied into ad.py from agents/analysis/fixedpoint/analyze.py): the interpolated
  crossing of claim = target between the adjacent targets where the setting goes from missing setup to meeting it,
  over the median claim at each target. Only settings with an **interpolated** F enter a fit or a bin.
- **The law's slopes** (`ad.py`, `fit_law`): r = T/F, e = (C − F)/F per run; within a setting a repeated (T, C) counts
  once; s⁻ = least-squares slope of e on (r − 1) **through the origin** over runs with r < 1; s⁺ the same over
  r > 1. This is the method that produced 0.59/0.29 and 0.20/0.65 (ideas/mechanism-law-fig.py).
- **Bins** (E5's S1/S2): tight r < 0.9, near 0.9–1.1, loose 1.1–1.5, very loose > 1.5; median e per bin.

## What was seen before this registration
- The full E5 record (E5_PREREG.md, E5_RESULT.md, all 46 audit runs incl. the 16 rebuilds) and E5b (GT2N kit smoke,
  a different image), the mechanism-law fits and figure, advanced-nodes.md. **T1 is therefore a retrodiction**: every
  outcome it scores was in the record before this file was written.
- Smoke batch smoke01 (workflow run 41566436932) and the grid-anchor pilots smoke02 (run 41567215999), tags
  `smoke-*`, excluded from every analysis: see the last section.
- No run of any registered arm.

## T1 — the law predicts E5's rebuilds (no farm time; a registered retrodiction)
Registered prediction (verbatim): *"Fit s⁻/s⁺ on the 30 ASAP7 grid runs only, then predict the 16 rebuilds' claims
and pass/fail. Pass: ≥13 of 16 pass/fail calls right AND median claim error ≤3%."*
- Data: farm/qa/E5/e5_analysis.json (committed E5 record): grid = the 30 `e5g-*` runs, rebuilds = the 16 `e5k-*`.
- Fit: F per setting from its **grid runs only** (E5's crossing; interpolated settings only); s⁻, s⁺ as defined.
- Forecast, for each rebuild run at its actual target R in its setting: Ĉ = F + s·(R − F), s = s⁻ if R < F else s⁺;
  called pass iff Ĉ ≤ R (equivalently R ≥ F). A rebuild whose setting has no interpolated grid F gets no forecast and
  counts as a wrong call (left out of the median error). Claim error = |Ĉ − C|/C.
- **Pass:** ≥ 13 of 16 calls right AND median claim error ≤ 3%. Script: `python3 farm/qa/AD/ad.py t1`.
- Beside (no criterion): the claim itself as the forecast (Ĉ = the chain winner's claim C0; every rebuild at or above
  C0 called pass), and all-fail calls.

## T2 — flow or node (the decisive test)
Registered prediction (verbatim): *"(a) ORFS on sky130hd, gcd/aes/ibex, E5's grid, 30 runs: prediction s⁻ ≤ 0.35 and
s⁺ ≥ 0.45; the "node, not flow" outcome is s⁻ ≥ 0.45. (b) ORFS on ASAP7 with ABC told the clock (one-line patch adding
`-D <target ps>` to `abc_args` in synth_preamble.tcl; prove it took effect by grepping the synthesis log), 30 runs:
prediction s⁻ ≥ 0.35; the "not synthesis" outcome is s⁻ < 0.30."*

**Runs** (farm/qa/AD/grid.json; E5's grid rule transferred to each platform): per design, S0 = the shipped config at
{0.70, 0.85, 1.00, 1.40}·P0; S1 = CORE_UTILIZATION lowered by E5's points (15 for gcd/aes, 10 for ibex) and S2 = the
design's density knob raised (PLACE_DENSITY_LB_ADDON + 0.20 where the design sets it, else PLACE_DENSITY at E5's
value) at {0.80, 1.20, 1.45}·P0; targets to the nearest 5 ps. On ASAP7 (T2b) P0 is the shipped period, as in E5. On
sky130hd and GT2N P0 is anchored at the pilot-estimated clock of the shipped setting (**Grid anchor**, below: a design
change forced by smoke01, where sky130hd gcd's shipped 1.1 ns sat 2.1× below its own claim, so E5's grid around the
shipped period would never have reached a passing target).

| arm | platform | design | P0 | S0 targets | S1 | S2 | S1/S2 targets |
|---|---|---|---|---|---|---|---|
| T2a `ads` | sky130hd | gcd | P0 from the grid anchor | {0.70, 0.85, 1.00, 1.40}·P0 | CORE_UTILIZATION 23 (shipped 38) | PLACE_DENSITY 0.90 (platform 0.60) | {0.80, 1.20, 1.45}·P0 |
| T2a `ads` | sky130hd | aes | P0 from the grid anchor | {0.70, 0.85, 1.00, 1.40}·P0 | CORE_UTILIZATION 20 (35) | PLACE_DENSITY_LB_ADDON 0.40 (0.2) | {0.80, 1.20, 1.45}·P0 |
| T2a `ads` | sky130hd | ibex | P0 from the grid anchor | {0.70, 0.85, 1.00, 1.40}·P0 | CORE_UTILIZATION 40 (50) | PLACE_DENSITY_LB_ADDON 0.45 (0.25) | {0.80, 1.20, 1.45}·P0 |
| T2b `adb` | asap7 | gcd, aes, ibex | 310, 380, 900 ps (shipped) | E5's exactly | E5's | E5's | E5's |

**Grid anchor (sky130hd and GT2N).** P0 = 5·round(F_pilot/5), where F_pilot is E5's `crossing` over the shipped
setting's pilot runs (all smoke-tagged, excluded from every analysis): smoke01's run at the shipped period (gcd) and
its one rebuild (sky130hd gcd at 2325 ps), and smoke02's pilots (sky130hd aes at 3600/5760/9000 ps, ibex at
8000/12800/20000 ps, GT2N aes at 350/490/700 ps, sky130hd gcd at 2905 ps, GT2N gcd at 260 ps). Computed by
`ad.py anchor` (E5's `crossing` over the pilot points, the median claim per target; if no adjacent pair of pilots
goes from missing setup to meeting it, F_pilot is E5's extrapolated crossing). The rule is registered here; its
output (P0 and the targets per design) is written into farm/qa/AD/grid.json in the dispatch commit, before any
non-smoke run, and listed in the result. This puts each grid where E5's sat relative to F (E5's shipped periods were
0.6–13% from F), so both sides of F are sampled whatever the slopes turn out to be. The shipped periods (sky130hd gcd
1.1 ns, aes 3.6 ns, ibex 8.0 ns; GT2N gcd 170 ps, aes 350 ps) are not used beyond the pilots.

- **(a) metric:** s⁻ and s⁺ of the law fitted on the 30 `ads-*` grid runs (F from those runs). **Prediction held
  ("flow")** iff s⁻ ≤ 0.35 and s⁺ ≥ 0.45. **"Node, not flow"** iff s⁻ ≥ 0.45. Anything else (0.35 < s⁻ < 0.45, or
  s⁻ ≤ 0.35 with s⁺ < 0.45): neither; the prediction failed. Not computable if a side has no runs with an
  interpolated F (reported as such).
- **(b) metric:** s⁻ of the law fitted on the 30 `adb-*` grid runs. **Prediction held ("synthesis")** iff s⁻ ≥ 0.35;
  **"not synthesis"** iff s⁻ < 0.30; 0.30–0.35 inconclusive.
- **The ABC patch, and why it is more than one line (a design change made before launch, not seen by Avi).** ORFS
  passes ABC its own script *files* (abc_speed.script; abc_speed_gia_only.script on the `abc_new` path), and Yosys
  substitutes a `-D` delay target only where the string `{D}` appears in an inline script or its built-in default
  (passes/techmap/abc.cc and abc9_exe.cc). Appending `-D <ps>` to `abc_args` alone therefore changes nothing. The
  patch (`orfs_run.sh`, applied in each T2b run's fresh container) (1) appends `-D <target ps>` to `abc_args` in
  synth_preamble.tcl, as planned, and (2) passes ORFS's own ABC script inline with `{D}` appended to the three
  commands that take a delay target, `&nf`, `upsize` and `dnsize` (where Yosys's own constrained default script puts
  them), on both mapping paths (synth_preamble.tcl for `abc`; the `abc9.script` scratchpad in synth.tcl for
  `abc_new`; the arithmetic-operator modules' `+&dch;&nf -R 5;` in synth_wrap_operators.tcl). With no target the
  inline script is the stock one.
- **gcd and aes switch to Yosys/ABC** (`SYNTH_USE_SYN=0`, ORFS's default synthesizer): their shipped ASAP7 configs use
  OpenROAD's `syn`, which has no ABC delay target to set. ibex already uses Yosys/ABC. So T2b's gcd and aes differ
  from E5 in two ways (synthesizer and target); a **descriptive control** (`adc-*`, 20 runs: the same gcd and aes grid
  through Yosys/ABC without the target) separates them. No prediction rides on the control.
- **Proof the patch took effect** (registered check, per run): the synthesis log carries the `abc`/`abc_new` command
  with `-D <target>` and the patch's `AD-ABC-D` line with the inline script (`run.json` `abc_d_log_hits` ≥ 1,
  `ad_abc_evidence.txt`); and, per design, the mapped netlist (Yosys `1_2_yosys.v`, sha1 in `run.json`) is not the
  same at every target. If a design's netlist is identical at all ten targets, T2b is reported for that design as
  "patch ran but ABC's mapping did not depend on the target" and the verdict says so.
- **Script:** `python3 farm/qa/AD/ad.py analyze` (blocks T2a, T2b; E5's own grid-only and grid+chain fits beside).

## T3 — the re-time judge (ASAP7 only)
Registered prediction (verbatim): *"Replay the 9 ASAP7 winners (and the 7 pushed sky130 winners only if LibreLane
plumbing is quick; otherwise ASAP7 only and say so in the PREREG) and run STA on each as-built layout at its corrected
claim (port paths corrected by 0.8, per mechanism-law.md §2) under the registered judge. Prediction: ≥14 of 16 (or ≥8
of 9 if ASAP7 only) pass; aes S0 meets 385 ps."*
- **ASAP7 only.** The 7 sky130 winners were built by LibreLane on the main-branch farm, whose jobs keep no layout
  database; re-timing them needs a LibreLane replay that keeps the ODB/SPEF plus a 9-corner STA script, which is not
  quick tonight. The criterion is therefore **≥ 8 of 9 pass, and aes S0 meets 385 ps**.
- **Runs** (`adr-<design>-<rank>`): E5's 9 winners (top 3 per design by AutoTuner's score: e5g-gcd-001/005/002,
  e5g-aes-003/005/001, e5g-ibex-003/008/002) re-run with their exact setting and clock. E5 showed the flow is
  deterministic (identical inputs gave identical slacks, hold and area on four CPU models), so a replay rebuilds the
  same layout; each replay is checked against E5's record (setup WS and hold WS within 0.01 ps).
- **Corrected claim** (from the winner's own path groups at its asked clock T0): C* = max(T0 − WS_r2r,
  T0 − WS_port/0.8), WS_port = min(WS_from-inputs, WS_to-outputs); **T\* = ceil5(C\*)**. (I/O delays are 20% of the
  clock at every port, so a port path's slack moves 0.8 per unit of clock; register paths move 1:1.)
- **Re-time** (ad_hook.tcl part 2, inside the finish step after extraction; no design change): re-read the run's own
  constraint.sdc with `set clk_period` replaced, then `set_propagated_clock [all_clocks]` as ORFS's finish step does;
  measure at T0 (must reproduce the flow's own finish WS within 0.01 ps, else the run's re-time is flagged as not
  valid) and at T\*.
- **Judge at T\*:** setup WS ≥ 0 and hold WS ≥ 0 at T\*, the layout's detailed-route DRC = 0. A replay without a valid
  re-time counts as a fail. **aes S0** = the 265 ps aes layout (e5g-aes-001, chain e5k-aes-3; §2's example): it must
  have T\* = 385 ps and pass there. **Prediction held** iff ≥ 8 of 9 pass and aes S0 meets 385 ps.
- **Script:** `ad.py analyze` (block T3).

## D — three nodes, one flow
Registered prediction (verbatim): *"Per advanced-nodes.md: the 7 nm grid and top-3 rebuilds repeated on sky130hd and
GT2N inside the same pinned ORFS image; prediction ≥55% of the new 7 nm-style winners fail their first rebuild, and
ORFS-on-sky130hd's tight-bin overclaim lands nearer ASAP7's (5.6%) than LibreLane's (14.5%)."*
- **Runs.** sky130hd: T2a's 30 grid runs (the same runs serve both) plus the top-3 chains per design (`adsk-*`).
  GT2N: gcd and aes (GT2N ships no ibex), E5's grid rule (20 runs, `adg-*`) plus top-3 chains (`adgk-*`):

| platform | design | P0 (grid anchor) | S0 targets | S1 | S2 | S1/S2 targets |
|---|---|---|---|---|---|---|
| gt2n | gcd | P0 from the grid anchor (shipped 170 ps) | {0.70, 0.85, 1.00, 1.40}·P0 | CORE_UTILIZATION 10 (shipped 25) | PLACE_DENSITY 0.90 (0.35) | {0.80, 1.20, 1.45}·P0 |
| gt2n | aes | P0 from the grid anchor (shipped 350 ps) | {0.70, 0.85, 1.00, 1.40}·P0 | CORE_UTILIZATION 15 (30) | PLACE_DENSITY_LB_ADDON 0.40 (0.20) | {0.80, 1.20, 1.45}·P0 |

- **Chains run on the runner** (`run_group.py await_chains`): once all 10 grid runs of a design have landed (E5's
  `--require-complete`), the job reads them from this workflow run's artifacts, picks the top 3 by AutoTuner's score
  and runs E5's chain rule. Nobody picks a winner by hand.
- **D1 metric:** over the new winners (sky130hd 9 + GT2N 6 = 15 if every chain starts), the fraction whose first
  rebuild fails the judge (a winner that already passed at its own claim, R1 ≥ T0, is its own first rebuild and
  passes, as in E5; a first rebuild without metrics fails). **Held** iff the fraction is ≥ 55% (≥ 9 of 15).
- **D2 metric:** the median claim error in the tight bin (r < 0.9) on ORFS-sky130hd, E5's S1 method (all sky130hd
  grid and chain runs; F per setting from all of them). **Held** ("nearer ASAP7") iff the median is above −10.05%,
  the midpoint of ASAP7's −5.6% and LibreLane's −14.5%; else "nearer LibreLane". Fewer than 3 tight points:
  insufficient. (advanced-nodes.md's stricter wording, "within 4 points of −5.6%", is reported beside.)
- **Script:** `ad.py analyze` (block D).

## Reported beside (no criterion)
Per-design slopes; bins near/loose/very loose; port vs register limits; E5's own grid-only and grid+chain fits; the
control's slopes; per-design netlist hashes (T2b, control); GT2N's bins; kept clock ÷ claim per chain; the T3 replay
checks and slack at T\*; run times.

## What each outcome means (said before the runs)
- T1 passes: the law, fitted on grid runs alone, already knows which E5 rebuilds fail and roughly where their claims
  land. T1 fails: two constants fitted on 9 settings do not carry to the rebuilds; the law is a median description,
  and only the rebuild judges. Either way it is a retrodiction and is labelled so.
- T2a held (s⁻ ≤ 0.35, s⁺ ≥ 0.45): ORFS at 130 nm looks like ORFS at 7 nm, so the constants belong to the flow.
  "Node, not flow" (s⁻ ≥ 0.45): ORFS at 130 nm looks like LibreLane at 130 nm; the constants are per node — still a
  law, but the 7 nm asymmetry is the node. Neither: the slopes move with both.
- T2b held (s⁻ ≥ 0.35): telling ABC the clock steepens ORFS's tight-side response toward LibreLane's, naming target-
  aware synthesis as a mechanism. "Not synthesis" (s⁻ < 0.30): the synthesis door is closed; the tight-side slope
  comes from P&R effort/repair, which is sharper advice for engineers who over-constrain synthesis.
- T3 held: below F a pushed layout already meets its corrected claim; re-timing the layout in hand is a free judge
  and the rebuild is the lazier build. T3 fails: the claim is a guess about the layout too; the thesis strengthens.
- D1 held: claims overclaim at 130 nm and 2 nm in ORFS as at 7 nm; one rebuild catches it on every node. Failed
  (< 55%): in ORFS the claim mostly holds at these nodes; the failures concentrate where E5 found them.
- D2 held: in one flow the tight-side overclaim is ORFS-sized at 130 nm too (flow); failed: it is LibreLane-sized
  (node).

## Budget, order, decision times, handling
- About 150 runs, ~30 flow-hours, ≤ 4 jobs at once, one workflow run (one matrix, priority order): T2 grids
  (sky130hd 30, ASAP7 30), sky130hd chains, T3 (9), GT2N grid (20) and chains, control (20).
- T2's verdicts are computed when its 60 grid runs have landed (and for this night's report on what has landed by
  07:00 ET Nov 3, labelled partial if incomplete). D and T3 when their runs land. Hard stop: Wed Nov 4 23:00 UTC;
  what has not landed then is reported as not run.
- Infrastructure failures (runner lost, image pull, missing artifact, job timeout): the same spec is re-dispatched
  once with the same tags. A flow error the retry reproduces is a result: a grid run without metrics never wins; a
  rebuild without metrics fails the judge; a setting without an interpolated F leaves the fit.
- Nothing in the grids, the chain rule, the judge, the fits or the tests changes after this file is hashed; any
  deviation is logged in the result with its reason.

## Caveats known in advance
1. One corner per platform (ASAP7 FF, sky130hd TT, GT2N TT); ASAP7 and GT2N are predictive/academic PDKs.
2. ORFS's ASAP7 gcd and aes normally synthesize with OpenROAD's `syn`; T2b moves them to Yosys/ABC (control beside).
3. The ABC patch adds `{D}` to ORFS's own scripts; it is the minimal change that makes `-D` reach ABC, not ORFS's
   or LibreLane's script.
4. S1/S2 and the 5 ps grid were transferred by fixed rules (above) that Avi did not see; GT2N gcd's S1 (10%
   utilization) is very sparse.
5. Small samples: 9 settings per node, 3 winners per design; slopes are least-squares lines through few settings,
   with no significance claimed.
6. The law's constants and E5's numbers were seen; only the tests above are predictions.
7. ORFS's gt2n platform ships no OpenRCX rules: GT2N's post-route timing uses ORFS's global-route parasitic
   estimates (the platform's own finish STA), unlike ASAP7 and sky130hd (OpenRCX).
8. One T3 outcome (the gcd S0 215 ps layout re-timed at 355 ps) was seen in smoke and is disclosed below.

## Smoke and pilots (seen before this registration; smoke-tagged, excluded from every analysis)
Commit eb145bf (smoke01, workflow run 41566436932, 02:29–02:34Z) and d1dd349 (smoke02 pilots, run 41567215999).
Every flow below completed with detailed-route DRC 0 and met hold.
- **sky130hd end to end** (smoke-ads-gcd, shipped config at its shipped 1100 ps): 64 s of flow; WS −1221.8 ps →
  claim 2321.8 ps, 2.1× the shipped period (register-to-register limited). OpenRCX ran (sky130hd ships RCX rules).
- **Runner-side chain** (sm-chain job): it fetched the sky130hd run's artifact from the same workflow run through the
  REST API one minute after upload, selected it, and rebuilt at ceil5(2321.8) = 2325 ps: WS −112.7 ps, claim
  2437.7 ps, failed. So the claim rose 0.09 ps per ps of target here, and the shipped 1.1 ns is far below what this
  setting meets: E5's grid around the shipped period (770–1595 ps) would have failed at every target. Hence the
  Grid anchor.
- **GT2N in the same image** (smoke-adg-gcd, shipped config at its shipped 170 ps): 70 s; WS −46.2 ps → claim
  216.2 ps (1.27× shipped; limited by a register-to-output path). The gt2n platform ships no OpenRCX rules, so its
  post-route STA uses ORFS's fallback, global-route parasitic estimates ("OpenRCX is not enabled for this platform.
  Falling back to global route-based estimates"). This is the platform's own judge and stays; it is a caveat.
- **T3 re-time hook** (smoke-adr-gcd-1, a replay of E5's winner e5g-gcd-001, gcd S0 at 215 ps): the replay gave
  WS −111.4230 ps and hold +41.9131 ps, E5's numbers to the digit (claim 326.423 ps). Re-reading the constraints at
  T0 reproduced the flow's WS and hold exactly. Corrected claim C\* = max(322.91, 215 + 111.42/0.8 = 354.28) →
  T\* = 355 ps, where the 215 ps layout had WS +0.577 ps (port path), register paths +32.1 ps, hold +41.9 ps. (This
  is one of the nine T3 layouts; its outcome was seen in smoke and is disclosed here. The registered T3 run
  `adr-gcd-1` repeats it.)
- **ABC patch, `abc` path** (ASAP7 gcd through Yosys, `SYNTH_USE_SYN=0`): the log shows `abc -script +...&nf,{D}...
  -D 215` and the `AD-ABC-D` line. The mapped netlist with the target was **identical at 215 and 450 ps** (sha1
  fb441a28, 314 cells, 38.258 µm²) and differed from the run without a target (cc7bef9c, 314 cells, 38.652 µm²).
  Reading: both targets are slack from ABC's wire-free view (its delay estimate of gcd is below 215 ps), so ABC
  recovers area to the same netlist at both; the target changes the netlist once, not per target. Claims: 363.1 ps at
  215 (with target), 350.8 ps at 215 (without), 406.2 ps at 450 (with target, passed); E5's `syn` gcd claimed 326.4
  ps at 215.
- **ABC patch, `abc_new` path** (ASAP7 ibex, synthesis only): the patched inline scripts reached `abc_new` (log),
  ABC exited with code 134 on every module exactly as in E5 (caveat 10 of E5_RESULT), and the netlist was
  **identical at 630 and 1305 ps** (sha1 364246e8) with the same cell list and area (2118.43 µm²) as without a target
  (sha1 dda12017; the hashes differ by the `abc9_script` attribute text the patch changes). So on ibex the target
  does not reach the mapping at all within the grid's range.
- **What this means for T2b, written before any T2b run:** in this flow at 7 nm, telling ABC the clock the way the
  plan specifies leaves the netlist the same at every grid target for gcd and ibex (aes untested). T2b runs as
  registered; its pre-declared netlist check will show per design whether the mapping varied, and the verdict will
  carry that. The registered prediction is unchanged (it is the plan's, not ours). Where the netlist is the same at
  every target, s⁻ can move only through placement, CTS and routing, so a "not synthesis" outcome there would mean
  "ABC told the clock is still clock-blind at these targets", not that target-aware synthesis can never matter.
- **Pilots (smoke02)** for the grid anchor: gcd's were seen before this file was hashed: sky130hd gcd at 2905 ps met
  setup (WS +97.9 ps, C = 2807.1 ps), so its F lies between 2325 and 2905 ps; GT2N gcd at 260 ps met setup
  (WS +0.97 ps, C = 259.0 ps), so its F lies between 170 and 260 ps. The aes and ibex pilots were still running when
  this file was hashed; their values enter only through the anchor rule.
