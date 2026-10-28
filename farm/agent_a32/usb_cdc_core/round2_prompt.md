You are tuning the settings of an open-source chip design flow (LibreLane/OpenROAD on the SkyWater sky130 130 nm
process) for one design. Use ONLY the information in this message: do not read files, run commands, search, or use
anything you may know about other runs or designs. Reply with the JSON described at the end and nothing else.

GOAL. Find settings that let this design pass signoff at the shortest clock period. Each run is scored by its effective
clock T_eff = (clock target it was given) - (worst setup slack over 9 signoff corners); lower is better. A run counts
only if it is FEASIBLE: hold slack >= 0 at every corner, zero router DRC errors, and no more slew/capacitance violation
pins (summed over the 9 corners) than the bar, which is set by the stock flow's run on this design. Note: T_eff from a
run aimed at a much looser or tighter target can be optimistic; the best run will later be re-checked at its T_eff.

DESIGN. usb_cdc_core: USB CDC device core (ultra-embedded). Default clock period 15.6 ns. Stock flow: about ? standard cells. Bar: 309
slew/cap pins.

KNOBS (the only things you can set; give every knob, within these ranges):
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

HISTORY on this design (10 runs so far: 8 'start' runs are settings found on other designs and applied unchanged;
'round' runs are your own earlier proposals, with your rationale). Each run shows its setting and a signoff summary.
- start blabla [x6z-usb_cdc_core-009] clock target 14.48 ns -> T_eff 9.018 ns, FEASIBLE
  setting {"period_frac": 0.928473063355609, "FP_CORE_UTIL": 27, "density_delta": 25, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3734844189074291, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.16520668545533518, "DESIGN_REPAIR_MAX_SLEW_PCT": 39, "DESIGN_REPAIR_MAX_CAP_PCT": 18, "RC_MODEL": "orfs"}
  setup: worst slack +5.462 ns at ss 100C 1.60V max-RC (reg-to-reg worst +8.037 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.095 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 11 slew/cap pins summed over corners (bar 309); worst corner max-slew 11, max-cap 0; fanout violations 0
  cells: 3883 std cells, 280 timing-repair buffers; std-cell area 27,435 um2; utilisation 34%
  routing: wirelength 57,323 um (pre-route estimate 52,990); detailed-route DRC by iteration [45, 14, 11, 0, 0], final 0
  clock: skew 0.289 ns (setup) / -0.348 ns (hold); power 3.06 mW; flow runtime 3.0 min
- start des [x6z-usb_cdc_core-010] clock target 7.54 ns -> T_eff 7.300 ns, FEASIBLE
  setting {"period_frac": 0.48352759747215784, "FP_CORE_UTIL": 27, "density_delta": 19, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.16636921385131967, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.25116636617682997, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 40, "RC_MODEL": "cap213"}
  setup: worst slack +0.240 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.240 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.093 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 309); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3596 std cells, 227 timing-repair buffers; std-cell area 26,673 um2; utilisation 33%
  routing: wirelength 60,336 um (pre-route estimate 53,108); detailed-route DRC by iteration [473, 187, 147, 0], final 0
  clock: skew 0.285 ns (setup) / -0.344 ns (hold); power 5.76 mW; flow runtime 3.7 min
- start bm64 [x6z-usb_cdc_core-011] clock target 7.86 ns -> T_eff 7.638 ns, FEASIBLE
  setting {"period_frac": 0.503863953041454, "FP_CORE_UTIL": 21, "density_delta": 14, "SYNTH_STRATEGY": "DELAY 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.24619915855228341, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.10560593983481525, "DESIGN_REPAIR_MAX_SLEW_PCT": 30, "DESIGN_REPAIR_MAX_CAP_PCT": 11, "RC_MODEL": "orfs"}
  setup: worst slack +0.222 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.222 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.091 ns at ff -40C 1.95V min-RC; 0 violations; 180 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 309); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3763 std cells, 460 timing-repair buffers; std-cell area 27,204 um2; utilisation 28%
  routing: wirelength 65,296 um (pre-route estimate 57,716); detailed-route DRC by iteration [8, 1, 1, 0, 0], final 0
  clock: skew 0.289 ns (setup) / -0.350 ns (hold); power 5.08 mW; flow runtime 3.9 min
- start ocs_blitter [x6z-usb_cdc_core-012] clock target 9.63 ns -> T_eff 7.804 ns, FEASIBLE
  setting {"period_frac": 0.6171955706800487, "FP_CORE_UTIL": 40, "density_delta": 15, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.32283309180712455, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.21234668380681754, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 29, "RC_MODEL": "cap213"}
  setup: worst slack +1.826 ns at ss 100C 1.60V max-RC (reg-to-reg worst +3.489 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.093 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 309); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3360 std cells, 335 timing-repair buffers; std-cell area 26,550 um2; utilisation 48%
  routing: wirelength 50,905 um (pre-route estimate 46,408); detailed-route DRC by iteration [466, 120, 115, 2, 0], final 0
  clock: skew 0.283 ns (setup) / -0.344 ns (hold); power 4.52 mW; flow runtime 2.4 min
- start md5 [x6z-usb_cdc_core-013] clock target 7.75 ns -> T_eff 6.955 ns, FEASIBLE
  setting {"period_frac": 0.49666758392155613, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.17835233972832615, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.09022060448969806, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  setup: worst slack +0.795 ns at ss 100C 1.60V max-RC (reg-to-reg worst +1.435 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.085 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 309); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3617 std cells, 357 timing-repair buffers; std-cell area 27,020 um2; utilisation 37%
  routing: wirelength 56,909 um (pre-route estimate 52,209); detailed-route DRC by iteration [22, 3, 3, 0], final 0
  clock: skew 0.289 ns (setup) / -0.347 ns (hold); power 5.76 mW; flow runtime 3.7 min
- start picorv32 [x6z-usb_cdc_core-014] clock target 8.15 ns -> T_eff 7.556 ns, FEASIBLE
  setting {"period_frac": 0.5222176203433402, "FP_CORE_UTIL": 38, "density_delta": 5, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.2585143226133421, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.0285628051553697, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "stock"}
  setup: worst slack +0.594 ns at ss 100C 1.60V max-RC (reg-to-reg worst +1.934 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.073 ns at ss 100C 1.60V max-RC; 0 violations; 218 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 309); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3354 std cells, 341 timing-repair buffers; std-cell area 26,334 um2; utilisation 46%
  routing: wirelength 55,855 um (pre-route estimate 50,531); detailed-route DRC by iteration [452, 88, 56, 0], final 0
  clock: skew 0.304 ns (setup) / -0.348 ns (hold); power 5.00 mW; flow runtime 2.7 min
- start y_huff [x6z-usb_cdc_core-015] clock target 15.23 ns -> T_eff 10.052 ns, FEASIBLE
  setting {"period_frac": 0.976013443761732, "FP_CORE_UTIL": 37, "density_delta": 18, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.041485267124613805, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.03869271067313256, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 27, "RC_MODEL": "stock"}
  setup: worst slack +5.178 ns at ss 100C 1.60V max-RC (reg-to-reg worst +8.829 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.103 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 33 slew/cap pins summed over corners (bar 309); worst corner max-slew 33, max-cap 0; fanout violations 5
  cells: 3428 std cells, 206 timing-repair buffers; std-cell area 26,163 um2; utilisation 44%
  routing: wirelength 55,434 um (pre-route estimate 49,749); detailed-route DRC by iteration [501, 148, 134, 0], final 0
  clock: skew 0.294 ns (setup) / -0.347 ns (hold); power 2.66 mW; flow runtime 3.1 min
- start aes_cipher [x6z-usb_cdc_core-016] clock target 8.98 ns -> T_eff 9.032 ns, FEASIBLE
  setting {"period_frac": 0.5759360256713374, "FP_CORE_UTIL": 23, "density_delta": 7, "SYNTH_STRATEGY": "AREA 2", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.09845674949215728, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3225578512156802, "DESIGN_REPAIR_MAX_SLEW_PCT": 38, "DESIGN_REPAIR_MAX_CAP_PCT": 26, "RC_MODEL": "stock"}
  setup: worst slack -0.052 ns at ss 100C 1.60V max-RC (reg-to-reg worst -0.052 ns); TNS -0.38 ns; 8 violating endpoints at the target
  hold: worst slack +0.104 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 309); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3339 std cells, 425 timing-repair buffers; std-cell area 24,965 um2; utilisation 29%
  routing: wirelength 58,411 um (pre-route estimate 52,134); detailed-route DRC by iteration [468, 90, 58, 0], final 0
  clock: skew 0.288 ns (setup) / -0.347 ns (hold); power 4.79 mW; flow runtime 2.9 min
- round 1 [x8a-usb_cdc_core-001] clock target 7.02 ns -> T_eff 6.363 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.35, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  setup: worst slack +0.657 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.657 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.090 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 309); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3643 std cells, 386 timing-repair buffers; std-cell area 27,135 um2; utilisation 37%
  routing: wirelength 57,286 um (pre-route estimate 52,173); detailed-route DRC by iteration [439, 88, 76, 0], final 0
  clock: skew 0.282 ns (setup) / -0.345 ns (hold); power 6.33 mW; flow runtime 1.8 min
  (your rationale then: AREA 3 runs show a natural reg-to-reg path of ~6.1-6.4 ns at any target; DELAY 3/4 (~7.3-7.6) and AREA 2 (~9.0) are worse. The best run (md5 recipe, 6.955) is limited by a port path whose T_eff falls as the target tightens (IO constraints appear to scale with the period), so go to the floor target (frac 0.45 = 7.02 ns) and raise setup margins so repair aims near 6.6-6.7 ns. Hold, slew/cap (max 33 vs bar 309) and DRC have ample headroom. Keep cap213 (repair landed within ~0.01 ns of its margin). Setting 1: md5 recipe at floor target, 0.3/0.35 margins. Setting 2: maximal 0.4/0.4 margins, util 36, tighter slew/cap repair.)
- round 1 [x8a-usb_cdc_core-002] clock target 7.02 ns -> T_eff 6.302 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 36, "density_delta": 12, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.4, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.4, "DESIGN_REPAIR_MAX_SLEW_PCT": 30, "DESIGN_REPAIR_MAX_CAP_PCT": 25, "RC_MODEL": "cap213"}
  setup: worst slack +0.718 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.894 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.095 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 309); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3536 std cells, 412 timing-repair buffers; std-cell area 27,212 um2; utilisation 44%
  routing: wirelength 53,998 um (pre-route estimate 49,814); detailed-route DRC by iteration [398, 88, 75, 0], final 0
  clock: skew 0.290 ns (setup) / -0.345 ns (hold); power 6.47 mW; flow runtime 2.8 min
  (your rationale then: AREA 3 runs show a natural reg-to-reg path of ~6.1-6.4 ns at any target; DELAY 3/4 (~7.3-7.6) and AREA 2 (~9.0) are worse. The best run (md5 recipe, 6.955) is limited by a port path whose T_eff falls as the target tightens (IO constraints appear to scale with the period), so go to the floor target (frac 0.45 = 7.02 ns) and raise setup margins so repair aims near 6.6-6.7 ns. Hold, slew/cap (max 33 vs bar 309) and DRC have ample headroom. Keep cap213 (repair landed within ~0.01 ns of its margin). Setting 1: md5 recipe at floor target, 0.3/0.35 margins. Setting 2: maximal 0.4/0.4 margins, util 36, tighter slew/cap repair.)

TASK. Round 2 of 4. Propose exactly 2 NEW settings for this design (different from every setting above),
chosen to lower the best feasible T_eff, using what the signoff summaries tell you (for example which corner limits
setup, whether the worst path touches a port, hold-buffer counts, slew/cap pins against the bar, congestion, wire length
against the pre-route estimate). Reply with JSON only, in this form:
{"rationale": "<at most 120 words: what the reports suggest and why these settings>",
 "settings": [{<all 15 knobs>}, {<all 15 knobs>}]}
