You are guiding a Bayesian optimizer (Optuna's TPE sampler) that tunes the settings of an open-source chip design
flow (LibreLane/OpenROAD on the SkyWater sky130 130 nm process) for one design. Use ONLY the information in this message:
do not read files, run commands, search, or use anything you may know about other runs or designs. Reply with the JSON
described at the end and nothing else.

GOAL. Find settings that let this design pass signoff at the shortest clock period. Each run is scored by its effective
clock T_eff = (clock target it was given) - (worst setup slack over 9 signoff corners); lower is better. A run counts
only if it is FEASIBLE: hold slack >= 0 at every corner, zero router DRC errors, and no more slew/capacitance violation
pins (summed over the 9 corners) than the bar, which is set by the stock flow's run on this design. T_eff from a run
aimed at a much looser or tighter target can be optimistic: the best run will later be re-run at its T_eff, and then
again at the clock each passing re-run claims, and the result is the shortest clock that actually passes.

HOW THE SEARCH WORKS. The optimizer proposes 2 settings per round, for 4 rounds (8 runs), and learns from
every run's score and feasibility (including the start runs below). You do not propose settings. You write a POLICY:
you may PIN up to 8 knobs to fixed values. For every new proposal the optimizer uses your pinned values and
chooses all other knobs itself from the history. An empty policy {} leaves the optimizer unchanged. This is a revision: you see the
results of the rounds run under the earlier policies, and you may keep the policy, change pinned values, add pins or
remove pins.

DESIGN. xtea: XTEA block cipher (OpenCores). Default clock period 26.03 ns. Stock flow: about 321 standard cells. Bar: 0
slew/cap pins.

KNOBS (pin only these, within these ranges):
- period_frac (float: 0.45 to 1.0): clock target as a fraction of the design's default clock period
- FP_CORE_UTIL (int: 20 to 50): core utilisation, % (lower leaves room for wires and late repairs)
- density_delta (int: 5 to 30): placement density = utilisation + this many points (capped at 80)
- SYNTH_STRATEGY (cat: AREA 0 | AREA 1 | AREA 2 | AREA 3 | DELAY 0 | DELAY 1 | DELAY 2 | DELAY 3 | DELAY 4): Yosys/ABC synthesis script (AREA = smaller, DELAY = faster logic)
- SYNTH_ABC_BUFFERING (bool: true | false): insert buffers during synthesis
- SYNTH_SIZING (bool: true | false): resize gates during synthesis
- PL_TIMING_DRIVEN (bool: true | false): timing-driven global placement
- PL_ROUTABILITY_DRIVEN (bool: true | false): routability-driven global placement (spreads cells in crowded areas)
- RUN_POST_GRT_RESIZER_TIMING (bool: true | false): timing repair again after global routing
- RUN_POST_GRT_DESIGN_REPAIR (bool: true | false): slew/cap/fanout repair again after global routing
- PL_RESIZER_SETUP_SLACK_MARGIN (float: 0.0 to 0.4): extra setup margin (ns) placement-stage repair aims for
- GRT_RESIZER_SETUP_SLACK_MARGIN (float: 0.0 to 0.4): extra setup margin (ns) post-global-route repair aims for
- DESIGN_REPAIR_MAX_SLEW_PCT (int: 10 to 40): repair aims this % below the slew limit
- DESIGN_REPAIR_MAX_CAP_PCT (int: 10 to 40): repair aims this % below the capacitance limit
- RC_MODEL (cat: stock | cap213 | orfs): wire R/C assumed before routing: stock LEF values; cap213 = wire capacitance x2.13 (measured gap to signoff extraction in this flow); orfs = OpenROAD-flow-scripts per-layer values

HISTORY on this design (10 runs so far: 8 'start' runs are settings found on other designs and applied unchanged; 'round' runs were proposed by the optimizer under your policies).
Each run shows its setting and a signoff summary.
- start blabla [x6z-xtea-001] clock target 24.17 ns -> T_eff 9.998 ns, FEASIBLE
  setting {"period_frac": 0.928473063355609, "FP_CORE_UTIL": 27, "density_delta": 25, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3734844189074291, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.16520668545533518, "DESIGN_REPAIR_MAX_SLEW_PCT": 39, "DESIGN_REPAIR_MAX_CAP_PCT": 18, "RC_MODEL": "orfs"}
  setup: worst slack +14.172 ns at ss 100C 1.60V max-RC (reg-to-reg worst +20.004 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.100 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 0); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 429 std cells, 164 timing-repair buffers; std-cell area 2,969 um2; utilisation 50%
  routing: wirelength 4,373 um (pre-route estimate 4,435); detailed-route DRC by iteration [33, 34, 25, 0], final 0
  clock: skew 0.261 ns (setup) / -0.295 ns (hold); power 0.12 mW; flow runtime 1.2 min
- start des [x6z-xtea-002] clock target 12.59 ns -> T_eff 8.161 ns, FEASIBLE
  setting {"period_frac": 0.48352759747215784, "FP_CORE_UTIL": 27, "density_delta": 19, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.16636921385131967, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.25116636617682997, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 40, "RC_MODEL": "cap213"}
  setup: worst slack +4.429 ns at ss 100C 1.60V max-RC (reg-to-reg worst +8.399 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.099 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 0); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 332 std cells, 97 timing-repair buffers; std-cell area 2,664 um2; utilisation 49%
  routing: wirelength 4,508 um (pre-route estimate 4,375); detailed-route DRC by iteration [44, 20, 4, 0], final 0
  clock: skew 0.261 ns (setup) / -0.296 ns (hold); power 0.23 mW; flow runtime 1.2 min
- start bm64 [x6z-xtea-003] clock target 13.12 ns -> T_eff 6.472 ns, FEASIBLE
  setting {"period_frac": 0.503863953041454, "FP_CORE_UTIL": 21, "density_delta": 14, "SYNTH_STRATEGY": "DELAY 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.24619915855228341, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.10560593983481525, "DESIGN_REPAIR_MAX_SLEW_PCT": 30, "DESIGN_REPAIR_MAX_CAP_PCT": 11, "RC_MODEL": "orfs"}
  setup: worst slack +6.648 ns at ss 100C 1.60V max-RC (reg-to-reg worst +8.747 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.099 ns at ff -40C 1.95V min-RC; 0 violations; 26 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 0); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 432 std cells, 167 timing-repair buffers; std-cell area 2,894 um2; utilisation 40%
  routing: wirelength 3,956 um (pre-route estimate 3,944); detailed-route DRC by iteration [26, 18, 6, 0], final 0
  clock: skew 0.262 ns (setup) / -0.297 ns (hold); power 0.23 mW; flow runtime 0.7 min
- start ocs_blitter [x6z-xtea-004] no result
  setting {"period_frac": 0.6171955706800487, "FP_CORE_UTIL": 40, "density_delta": 15, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.32283309180712455, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.21234668380681754, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 29, "RC_MODEL": "cap213"}
  run stopped before signoff (flow_failed)
- start md5 [x6z-xtea-005] clock target 12.93 ns -> T_eff 6.874 ns, FEASIBLE
  setting {"period_frac": 0.49666758392155613, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.17835233972832615, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.09022060448969806, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  setup: worst slack +6.056 ns at ss 100C 1.60V max-RC (reg-to-reg worst +8.703 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.097 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 0); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 354 std cells, 97 timing-repair buffers; std-cell area 2,775 um2; utilisation 51%
  routing: wirelength 3,768 um (pre-route estimate 3,761); detailed-route DRC by iteration [24, 11, 13, 0], final 0
  clock: skew 0.262 ns (setup) / -0.295 ns (hold); power 0.23 mW; flow runtime 1.2 min
- start picorv32 [x6z-xtea-006] no result
  setting {"period_frac": 0.5222176203433402, "FP_CORE_UTIL": 38, "density_delta": 5, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.2585143226133421, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.0285628051553697, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "stock"}
  run stopped before signoff (flow_failed)
- start y_huff [x6z-xtea-007] clock target 25.41 ns -> T_eff 11.123 ns, FEASIBLE
  setting {"period_frac": 0.976013443761732, "FP_CORE_UTIL": 37, "density_delta": 18, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.041485267124613805, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.03869271067313256, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 27, "RC_MODEL": "stock"}
  setup: worst slack +14.287 ns at ss 100C 1.60V max-RC (reg-to-reg worst +21.260 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.115 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 0); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 355 std cells, 100 timing-repair buffers; std-cell area 2,874 um2; utilisation 66%
  routing: wirelength 4,023 um (pre-route estimate 3,966); detailed-route DRC by iteration [17, 6, 7, 0], final 0
  clock: skew 0.262 ns (setup) / -0.294 ns (hold); power 0.12 mW; flow runtime 1.0 min
- start aes_cipher [x6z-xtea-008] clock target 14.99 ns -> T_eff 6.864 ns, FEASIBLE
  setting {"period_frac": 0.5759360256713374, "FP_CORE_UTIL": 23, "density_delta": 7, "SYNTH_STRATEGY": "AREA 2", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.09845674949215728, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3225578512156802, "DESIGN_REPAIR_MAX_SLEW_PCT": 38, "DESIGN_REPAIR_MAX_CAP_PCT": 26, "RC_MODEL": "stock"}
  setup: worst slack +8.126 ns at ss 100C 1.60V max-RC (reg-to-reg worst +9.815 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.113 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 0); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 424 std cells, 172 timing-repair buffers; std-cell area 2,794 um2; utilisation 45%
  routing: wirelength 3,952 um (pre-route estimate 3,929); detailed-route DRC by iteration [35, 5, 7, 0], final 0
  clock: skew 0.261 ns (setup) / -0.296 ns (hold); power 0.20 mW; flow runtime 0.9 min
- round 1 [xah1-xtea-001] no result
  pinned by the policy then: {"period_frac": 0.45, "FP_CORE_UTIL": 22, "density_delta": 14, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "DESIGN_REPAIR_MAX_SLEW_PCT": 35, "RUN_POST_GRT_RESIZER_TIMING": true}
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 22, "density_delta": 14, "SYNTH_STRATEGY": "DELAY 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3937971007229673, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.30578629928515877, "DESIGN_REPAIR_MAX_SLEW_PCT": 35, "DESIGN_REPAIR_MAX_CAP_PCT": 13, "RC_MODEL": "orfs"}
  run stopped before signoff (flow_failed)
- round 1 [xah1-xtea-002] clock target 11.71 ns -> T_eff 6.738 ns, FEASIBLE
  pinned by the policy then: {"period_frac": 0.45, "FP_CORE_UTIL": 22, "density_delta": 14, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "DESIGN_REPAIR_MAX_SLEW_PCT": 35, "RUN_POST_GRT_RESIZER_TIMING": true}
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 22, "density_delta": 14, "SYNTH_STRATEGY": "DELAY 1", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.18534334549501152, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.13099229103832533, "DESIGN_REPAIR_MAX_SLEW_PCT": 35, "DESIGN_REPAIR_MAX_CAP_PCT": 10, "RC_MODEL": "orfs"}
  setup: worst slack +4.972 ns at ss 100C 1.60V max-RC (reg-to-reg worst +7.830 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.095 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 0); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 426 std cells, 158 timing-repair buffers; std-cell area 2,800 um2; utilisation 41%
  routing: wirelength 4,940 um (pre-route estimate 4,753); detailed-route DRC by iteration [54, 32, 21, 5, 0], final 0
  clock: skew 0.261 ns (setup) / -0.296 ns (hold); power 0.25 mW; flow runtime 1.4 min

POLICIES SO FAR (yours, with your rationale then):
- round 1: pins {"period_frac": 0.45, "FP_CORE_UTIL": 22, "density_delta": 14, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "DESIGN_REPAIR_MAX_SLEW_PCT": 35, "RUN_POST_GRT_RESIZER_TIMING": true}; rationale: Every feasible run is limited by a port path at ss/max-RC with big positive slack, and T_eff tracks the target (~0.2×target + 3.9-6 ns, i.e. IO delay scales with period), so pin period_frac at 0.45. Reg-to-reg needs only ~4.2-4.4 ns. Timing-driven placement gave the fastest port paths (~3.9-4.3 vs 5.2-6.0 ns); slew-repair targets >=30% added ~70 buffers and coincided with the best ones. Both flow failures had util 38-40 (final utilisation ~1.8x setting), so pin low util and moderate density. Routing is uncongested (DRC->0): no routability spreading. Post-GRT timing repair pinned on for the tighter confirmation re-runs; synthesis, RC model, margins left free to explore.

TASK. Write the policy for round 2 of 4, using what the signoff summaries tell you (for example which
corner limits setup, whether the worst path touches a port, hold-buffer counts, slew/cap pins against the bar,
congestion, wire length against the pre-route estimate). Reply with JSON only, in this form:
{"rationale": "<at most 120 words: what the reports suggest and why these pins>",
 "pins": {"<knob>": <value>, ...}}
