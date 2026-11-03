# F — pre-registration: do the field's own published ORFS winners hold at the clocks they claim?

Written 2026-11-03 (UTC; time in farm/prereg_hashes.txt) by the overnight workstream F agent, **before any registered
run** (tags `f-<config>-<k>`). Its SHA-256 is appended to farm/prereg_hashes.txt on branch qa-f-field before the
registered batch (r01) is pushed. Code frozen at the commit that adds this file (branch qa-f-field):
.github/workflows/f_field.yml and farm/qa/F/{run_f.py, flib.py, orfsagent_run.sh, edaenv_run.py, fetch_sources.sh,
configs.json, f_score.py}. Result: docs/qa_week/F_RESULT.md. Base: branch qa-e5-asap7 (E5's ASAP7/ORFS audit; its
chain rule is reused).

## Question
TrueClock's audits (sky130/LibreLane; E5 on ASAP7/ORFS) rebuilt AutoTuner's own top picks at their claimed clock
(asked period − worst setup slack, AutoTuner's `effective_clk_period`) and found the claims did not hold. Every
2025–26 paper that tunes or edits an OpenROAD flow with an AI agent reports the same score as its result (ECP). F asks
the question of the field's **own published winners**: take each published winning configuration, build it exactly as
published at its published target (does our build reproduce the published ECP?), then rebuild the same configuration
with the clock set to its claimed ECP. Does it run there?

## Search: who published an ASAP7 or sky130hd ORFS winner with a claimed ECP (checked 2026-11-02/03)
| Work | Platform, flow | Claimed ECP published? | Winning configuration published? | Status |
|---|---|---|---|---|
| **ORFS-agent** (Ghose, Kahng, Kundu, Wang; arXiv:2506.08332 v1 Jun 2025 → v3 30 Apr 2026; MLCAD 2025) https://arxiv.org/abs/2506.08332 | ASAP7 + sky130hd; aes, ibex, jpeg; ORFS commit ce8d36a (paper, README) | Yes, per design and tuner (e.g. v3 ASAP7 aes 425/426 ps, ibex 1174/1172 ps; v1 ORFS-agent aes 432, ibex 1248; AutoTuner 430/1188) | **No** for the paper's winners: every version prints only knob ranges, never the chosen values. **Yes** for the authors' run database: github.com/ABKGroup/ORFS-Agent @ 730f1fa, `AutoTuner-integration/ORFS-with-AutoTuner/output.json` (sha256 5df91e1c…), 3,116 runs of their AutoTuner-integration harness with every knob, the clock and post-route metrics; aes and ibex on both platforms (no jpeg) | **3 registered** (aes/asap7, ibex/asap7, aes/sky130hd): the DRC-clean run with the lowest `ECP_final` per design/platform. These are the authors' published runs, not the paper's table entries; their ECPs sit inside or at the edge of the range the paper reports (below). ibex/sky130hd: **deferred** for runtime (below). The paper's own winners: not reproducible from the publication (values not published) |
| **EDA-env** (Ghose, Kahng, Kothari, Pandey, Roy; invited, ICCAD 2026, DOI 10.1145/3831252.3848500) https://vlsicad.ucsd.edu/Publications/Conferences/436/c436.pdf | ASAP7 (53 tasks), Nangate45, sky130hd (3 completion tasks); ORFS fb65d5b48 + OpenROAD 5c5380c49a with patched scripts | Yes: ECP = T_eval − WNS at a fixed evaluation SDC; reward = 1000/ECP (GHz) in the artifact's submissions/index.json; headline AES 387.6 → 291.5 ps | **Yes**: Zenodo doi:10.5281/zenodo.22990248 (EDA-env-85-tasks.tar.gz, sha256 3f80927e…; mirror github.com/Ergodex-Labs/eda-env-iccad-26): every task package, the final agent (Kimi-k3) submission diff, the evaluator, the Dockerfile with the image pinned by digest | **11 registered**: every ASAP7 timing task whose final submission the authors report as passing its gate (001, 008, 011, 013, 016, 037, 054, 074, 075, 087, 097). Not registered: ASAP7 timing tasks reported as failing their gate (014, 031, 068, 084: no valid claim), Nangate45 tasks (out of scope) |
| **AuDoPEDA** (Ghose, Jang, Kahng, Lee; arXiv:2601.06268 v2 Feb 2026) https://arxiv.org/abs/2601.06268 | Timing (ECP) results on **Nangate45 only** (ariane133 3.59→3.43 ns at TCP 3.4; ariane136 3.78→3.41 at 3.0; bp_fe 1.71→1.65 at 1.53; swerv_wrapper 2.19→2.16 at 1.7); ASAP7/sky130hd appear only as ECP % change under a power objective; ORFS 93c42b / OpenROAD 7bc521 | Nangate45 only | The agent's OpenROAD code edits are not in the paper; they are published as prebuilt artifacts (Docker Hub abkgroupucsd/audopeda: 1.2 GB Apptainer SIF + 7.8 GB ORFS tarball, `batch_run.sh --for-ecp`) | **Not registered**: no ASAP7/sky130hd ECP winner (outside scope). The Nangate45 ECP winners look reproducible from the published binaries but are multi-hour flows with a 9 GB download per job; listed for follow-up |
| **ResizerAgent** (attributed to MLCAD 2026 in literature.md) | — | — | — | **Not found**: no paper, preprint or artifact under that name in web searches on 2026-11-02 (one earlier lens file reported the same). Nothing to reproduce |
| TicTacBench (Wang et al., arXiv:2609.23363) | LibreLane + OpenROAD; PDK not named; t_ECP = t − WNS, positive slack ignored | No per-task ECP | Anonymized code link; winning RTL not stated to be released | Not registered (not an ORFS flow; no published claim per winner) |
| PostEDA-Bench (arXiv:2605.06936); Jeon & Kim (DATE 2026, DC/Innovus on ASAP7); PDAgent-Bench (arXiv:2606.17253, Innovus); "Agentic AI for PD R&D" (ISPD 2026, normalized results only); "Progress and Roadmap…" (DAC 2026, Nangate45) | — | — | — | Not registered: no ORFS ASAP7/sky130hd winner with a published configuration (or a commercial flow) |

ORFS-agent paper range (best ECP per tuner, v1 and v3 tables), for reference: ASAP7 aes 425–432 ps, ibex 1172–1252 ps;
sky130hd aes 3.77–4.08 ns, ibex 9.99–10.42 ns. The database's four bests: aes/asap7 427.663 ps (inside), ibex/asap7
1254.219 ps (0.2 % above the range), aes/sky130hd 3.801 ns (inside), ibex/sky130hd 10.231 ns (inside; deferred).

## The 14 registered configurations (farm/qa/F/configs.json)
T0 = the published target (EDA-env: the task's evaluation clock; the flow itself is asked for the task's working clock,
in brackets). C0_pub = the published claim. Units ps (ASAP7) and ns (sky130hd).

| id | source | design / platform | T0 | C0_pub | published slack at T0 | settings (what the winner changed) |
|---|---|---|---|---|---|---|
| ee001 | EDA-env 001 | aes / asap7 | 385.5 (380) | 291.529 | +94.0 | ASAP7_USE_VT=SLVT; SETUP_SLACK_MARGIN=170 |
| ee008 | EDA-env 008 | jpeg / asap7 | 400 (400) | 530.690 | −130.7 | RVT+LVT+SLVT; ABC_SYN_ROUNDS 8; PLACE_DENSITY 0.55; SYNTH_WRAPPED_OPERATORS; SWAP_ARITH_OPERATORS; OPENROAD_HIERARCHICAL; own resize.tcl |
| ee011 | EDA-env 011 | ibex / asap7 | 1000 (1000) | 953.681 | +46.3 | SLVT+LVT+RVT; SETUP_SLACK_MARGIN 30 |
| ee013 | EDA-env 013 | aes / asap7 | 368.2 (380) | 354.247 | +14.0 | CORE_UTILIZATION 30; PLACE_DENSITY 0.35; LVT; ABC_CLOCK_PERIOD_IN_PS 340; SETUP_SLACK_MARGIN 28; RECOVER_POWER 0 |
| ee016 | EDA-env 016 | jpeg / asap7 | 560.5 (400) | 508.927 | +51.6 | LVT+RVT; ABC_CLOCK_PERIOD_IN_PS 420; SETUP_SLACK_MARGIN 150; ABC_SYN_ROUNDS 8; GPL_TIMING_DRIVEN; ENABLE_PLACE_REPAIR_TIMING; RECOVER_POWER 100 |
| ee037 | EDA-env 037 | sboxpipe / asap7 | 312 (400) | 176.510 | +135.5 | GPL timing/routability driven; SLVT; SETUP_SLACK_MARGIN 270 |
| ee054 | EDA-env 054 | aes / asap7 | 340 (380) | 309.946 | +30.1 | RVT+LVT+SLVT; ENABLE_PLACE_REPAIR_TIMING; SETUP_SLACK_MARGIN 78 |
| ee074 | EDA-env 074 | mult16 / asap7 | 653 (900) | 401.527 | +251.5 | SLVT+LVT+RVT; ABC_CLOCK_PERIOD_IN_PS 300; ABC_SCRIPT_FILE $(WS)/abc.script (file not in the submission); SWAP_ARITH_OPERATORS; Booth multiplier; Kogge-Stone adders; OPENROAD_HIERARCHICAL; GPL timing/routability; SETUP_SLACK_MARGIN 650 |
| ee075 | EDA-env 075 | adder64 / asap7 | 360 (400) | 222.743 | +137.3 | CORE_UTILIZATION 45; SLVT+LVT+RVT; ABC_CLOCK_PERIOD_IN_PS 200; ADDER_MAP_FILE empty; SETUP_SLACK_MARGIN 180 |
| ee087 | EDA-env 087 | mult16 / asap7 | 615 (900) | 462.727 | +152.3 | CORE_UTILIZATION 70; ABC_CLOCK_PERIOD_IN_PS 400; SLVT+LVT+RVT; SETUP_SLACK_MARGIN 417 |
| ee097 | EDA-env 097 | aes / asap7 | 340 (380) | 327.695 | +12.3 | LVT; SETUP_SLACK_MARGIN 62; TNS_END_PERCENT 85; CORE_UTILIZATION 62; PLACE_DENSITY 0.62 |
| oa-aes-a7 | ORFS-agent row 744 | aes / asap7 | 140.237 | 427.663 | −287.4 | UTIL 55.053; LB_ADDON 0.489; TNS 27; hier synth; GP/DP pad 2/0; DPO; CTS 29/82; layer adj 0.64/0.283 |
| oa-ibex-a7 | ORFS-agent row 1876 | ibex / asap7 | 604.088 | 1254.219 | −650.1 | UTIL 47.612; LB_ADDON 0.782; TNS 16; flat; pad 1/0; DPO; CTS 19/111; adj 0.438/0.394 |
| oa-aes-s130 | ORFS-agent row 2551 | aes / sky130hd | 3.3 | 3.80126 | −0.501 | UTIL 37.589; LB_ADDON 0.022; TNS 26; hier; pad 0/0; DPO; CTS 28/104; adj 0.191/0.347 |

Composition, stated before any run: 10 of the 14 claims come from runs that **met** timing at T0 (positive slack: all
EDA-env except 008); 4 come from runs that **missed** (ee008 and the three ORFS-agent rows, AutoTuner-style tight
targets).

**Deferred, not registered:** ORFS-agent row 2717 (ibex/sky130hd, asked 3.634 ns, published claim 10.231 ns, slack
−6.597 ns). Decided before any registered run, from smoke runtime only: a sky130hd aes row of the same database (asked
0.91 ns) was still in detailed routing after 51 min (smoke s02), so this ibex row (about 4× the cells) is expected to
need more than the 300-minute job limit for its replay plus first rebuild. Follow-up with its own pre-registration.

## Toolchains and the ORFS version gap
- E5's pinned image is openroad/orfs 26Q4-244-g202c7fccb (ORFS 202c7fccb, 2026-10-30). Neither publication used it:
  ORFS-agent names ORFS ce8d36a (image `openroad/orfs:v3.0-1548-gce8d36a7`, pushed 2024-10-07, digest
  sha256:6fe655d0d5f33e2f344ec4ce1641b613b7bb90ec4cda279d2407386ed78ff6b3), two years and many flow changes older (at
  ce8d36a7 ABC is given the clock through ABC_CLOCK_PERIOD_IN_PS; at 202c7fccb aes uses OpenROAD's clock-blind `syn`).
  EDA-env pins `openroad/orfs:26Q3-5-gfb65d5b48@sha256:699820f927f1bed72f3673047a5a58007c81d11365ea6fa5cb2cea9f13b61946`
  plus its patched flow scripts (its Dockerfile).
- **Handling: each configuration runs in its own publication's pinned image and harness, not in E5's.** F's numbers
  are therefore not pooled with E5's. Whether the environment matches is tested, not assumed: the replay at T0 must
  reproduce the published claim (gate below). Running the same configurations in E5's image would mix flow drift
  into the claim error; it is not done.
- **ORFS-agent harness** (farm/qa/F/orfsagent_run.sh): a line-for-line copy of their `run_or_job.sh` (github.com/
  ABKGroup/ORFS-Agent @ 730f1fa, AutoTuner-integration/AutoTuner/): every knob exported to the environment (not a make
  override); CLK_PERIOD (read by their SDC template, `clk_io_pct 0.2`) and ABC_CLOCK_PERIOD_IN_PS both = the asked
  period (their sky130hd runs pass the ns value as "ps" to ABC; reproduced as is); their `<design>_<tech>.mk`, their
  FASTROUTE_TCL with PIN/UP layer adjustments; fixed AR 1, RECOVER_POWER 0, GPL timing- and routability-driven;
  NUM_CORES=4; make target `tunereport`. Their IO_PLACER exports compare the tech name in upper case, so with the
  lower-case names their runs carry, none applies (same here). Their configs are fetched on the runner at the pinned
  commit and sha256-checked (farm/qa/F/fetch_sources.sh). Unknown: the exact OpenROAD binary their cluster sourced
  (`~/SCRIPT/open_road_setup`); the image is the build that ships with ORFS ce8d36a7.
- **EDA-env harness** (farm/qa/F/edaenv_run.py): the artifact's own evaluator code (worker.py `flow` and `measure`
  phases, its measure.tcl) in the image built from its own Dockerfile. Differences, all outside the measurement: no
  `--cpus 8 --memory 16g` (Docker refuses --cpus above the runner's 4 vCPUs; the flow still gets NUM_CORES=8 as the
  evaluator passes it); no starter replay and no functional (LEC/testbench) phase, which the TrueClock judge does not
  use (every registered submission edits only config.mk or flow scripts, never RTL).
- GitHub Actions ubuntu-latest runners (4 vCPU, 16 GB), one flow at a time per job.

## Definitions
- **Claim** C = asked period − worst setup slack after route (ORFS-agent harness: ORFS `finish__timing__setup__ws`,
  exactly their ECP_final; EDA-env: the evaluation clock − `wns` of its measure.tcl, exactly their ECP).
- **Replay** W = the published configuration run as published at T0. Its claim C0.
- **Reproduced** = the replay completed with metrics and |C0 / C0_pub − 1| ≤ 2 %. (The 2 % tolerance was set in
  f_score.py at 21:32 ET, before the first smoke result came back at 21:43 ET.)
- **Rebuild at clock X** = the same configuration with only the clock changed to X: ORFS-agent harness CLK_PERIOD =
  ABC_CLOCK_PERIOD_IN_PS = X; EDA-env: the working SDC the flow reads **and** the evaluation SDC both
  `set clk_period X` (where the task reads the SDC from the image, the edited copy is bind-mounted over it).
  Everything else stays as published, including knobs written in absolute ps (SETUP_SLACK_MARGIN,
  ABC_CLOCK_PERIOD_IN_PS in EDA-env submissions): they are the winner's settings. The rule is TrueClock's: ask the
  flow for the claimed clock and judge it there. For 9 of the 11 EDA-env tasks the published flow was asked for a
  different clock (the task's working SDC) than the one it was judged at; the rebuild asks for and judges at X.
- **Judge (pass)** at the asked clock: flow completed; worst setup slack ≥ 0; worst hold slack ≥ 0 (ORFS-agent
  harness: hold violation count 0, the same test); routing DRC count 0 (ORFS-agent: `detailedroute__route__drc_errors`;
  EDA-env: its drc_resolve). Corner: the one each flow uses (ASAP7 FF libraries; sky130hd tt 25 °C 1.80 V). No slew/cap
  criterion (E5 had none either).
- **Grid**: ceil to 5 ps (ASAP7, E5's rule) or 0.05 ns (sky130hd, the sky130 record's rule).
- **Chain** (stepped on the runner, flib.chain_next = E5's e5lib.chain_next with the grid as a parameter; checked
  identical on 20,000 random chains): R1 = ceil(C0); after a passing rebuild with claim C, rebuild at ceil(C) while
  below the smallest passing clock and above every failed clock below it; if the first rebuild fails, step back once
  to max(ceil(C1), R1 + grid); at most 4 rebuilds; kept clock = smallest passing clock. If the replay passed and
  R1 ≥ T0 there is no rebuild (not expected here: every registered passing claim sits at least 12 ps below its T0).
- **d1** = C1/C0 − 1, C1 = the first rebuild's own claim. Positive d1 = the claim was optimistic (too fast).

## Runs
- Batch r01 (farm/qa/F/batches/r01.json): 14 groups, one configuration each, at most 2 jobs at once, in this order
  (longest first): ee008, ee016, oa-aes-s130, ee011, oa-ibex-a7, oa-aes-a7, ee001, ee013, ee097, ee054, ee074, ee087,
  ee037, ee075. Tags `f-<id>-0` (replay), `f-<id>-1` (first rebuild), `f-<id>-2…4`.
- Two phases in one workflow run: `run` (each group: replay + first rebuild), then `cont` (after every group's
  primary phase: each chain continues from its chain file). The primary test needs only the first phase.
- Per job: flow timeout 4 h; no new flow starts after 240 min of job time (200 min for the jpeg and sky130hd groups);
  job timeout 300 min.

## Registered test (farm/qa/F/f_score.py `score`)
Population P = the reproduced configurations.
- **P1:** the median of d1 over P (first rebuilds with a claim) is ≥ +3 %.
- **P2:** at least one first rebuild in P fails the judge (a first rebuild without metrics after the one
  infrastructure retry counts as a failure and is left out of P1).
- **The prediction holds** iff P1 and P2. Otherwise it fails, and the result names which part.
- If |P| < 3 the test is **underpowered**: the verdict is still computed and labelled so.

## Prediction (from the plan, verbatim; not changed after any outcome)
"Across the published winning configurations you can reproduce, **the median claim is optimistic by ≥ 3 %, and at
least one published winner fails at its claim**."

Context, not a second prediction: the shared law (fixed-point analysis) says claims from runs that missed timing are
optimistic and claims from runs that met it are pessimistic (ASAP7: k = 1.25 failing, 2.9 passing). Ten of the 14
registered claims come from runs that met timing, so the law points against P1 on this population and towards P2
(the four missed-timing claims). The split by the sign of the replay's slack is reported beside the verdict for that
reason.

## What each outcome means
- **Holds:** the field's own winners, built as published, overclaim: report ECP only after a rebuild at it.
- **P2 without P1:** some published winners fail at their claim, but the typical claim is not optimistic: the bias is
  design-, flow- and regime-dependent, and only a rebuild tells you which case you are in (the plan's reading).
- **P1 without P2:** claims run slow at rebuild but the grid's headroom lets every first rebuild pass.
- **Neither:** the published claims held: on these winners the score was safe, and that is worth saying too.
- Configurations that do not reproduce (|gap| > 2 %) are a finding of their own: a published number not recoverable
  from the published materials. They are reported with their gap and their (descriptive) chains.

## Reported beside, no criterion
P2 with **setup only** (which part of the judge each failure breaks: setup, hold, DRC). EDA-env's own gates check setup
(or ECP) and DRC but not hold, and the ORFS-agent database rows carry hold violations at their own targets, so a
published winner can fail the TrueClock judge on hold at any clock; the result says so wherever that happens.
Per source and per sign of the replay slack: median d1, failures; d1 against the published claim (C1/C0_pub − 1); kept
clock ÷ C0 for finished chains; the reproduction gap per configuration; whether the rebuild asked for a tighter or a
looser clock than the published working clock; setup/hold/DRC detail and area/power at the first rebuild.

## Decision times and handling
- The registered verdict is computed once every registered replay and every first rebuild of a reproduced
  configuration has landed. An interim reading at 2026-11-03 12:00 UTC (07:00 ET) on what has landed is labelled
  INTERIM. Chains are reported as they land; final report by 2026-11-11.
- Infrastructure failures (runner lost, image pull/build failure, missing artifact, job timeout): the same group is
  dispatched once more with the same tags. A flow error that the retry reproduces is a result: a replay without
  metrics → not reproduced; a first rebuild without metrics → fails the judge.
- Nothing in the configurations, the harnesses, the judge, the chain rule or the test changes after this file is
  hashed. Deviations are logged in F_RESULT.md with their reason.

## Smoke runs seen before this registration (tags `smoke-f-*`; plumbing only, never analyzed)
Smoke runs use configurations that are **not** registered, so no registered outcome was seen before this file.
- **s01** (workflow run 41566134694, commit d6d9360):
  - ORFS-agent harness: output.json row 1564 (aes/asap7, the database's second-best, not registered) at its own
    target 263.597 ps in the ce8d36a7 image: **bit-identical to the published row** on all 13 metrics it records (setup
    WS −166.407 ps, TNS −24555.1, 175 setup and 65 hold violations, power 0.229728 W, utilization 0.529465, 1340 repair
    buffers, routed wirelength 77945, 171721 vias, DRC 0, CTS WS −150.983, CTS wirelength 64700.3) → claim 430.004 ps
    = the published ECP_final. 823 s of flow. The ORFS-agent environment is reproduced exactly.
  - EDA-env path: the driver crashed before any flow (its case directory was not created); fixed in commit de8f3d0.
- **s02** (workflow run 41567954983, commit de8f3d0):
  - EDA-env path, replay mode: task 018 (mult16/asap7 completion task, not registered) at its evaluation clock 900 ps:
    the evaluator's flow and measure phases ran (105 s of flow, 6 s of measurement); wns +235.0 ps, whs +32.0 ps, DRC
    0 → claim 665.0 ps; the judge read it correctly. Image built from the artifact's Dockerfile in 75 s.
  - EDA-env path, rebuild mode: crashed before any flow (the driver opened each SDC for writing before reading it, so
    it found no `set clk_period` line). Fixed (read, then write); the edited task copy was then checked locally for
    tasks 001 (image SDC, bind mount) and 008 (workspace SDC): working SDC, evaluation SDC, targets.json and the
    mounted image SDC all carry the new clock; a replay leaves the task untouched.
  - ORFS-agent harness on sky130hd: output.json row 2322 (aes/sky130hd, the database's second-best, not registered)
    at its own target 0.91 ns. All knobs reached the environment as their script exports them (logged); synthesis,
    floorplan, placement, CTS and global route completed; after 51 min it was still in detailed routing (7th
    iteration, about 1,200 violations) and the job was cancelled to keep to one workflow run at a time. So the
    sky130hd path was exercised through global route but not to the finish report; its runtime led to deferring
    ibex/sky130hd (above).
- **s03** (workflow run 41573339561, commit f2776dd), EDA-env rebuild mode after the fix:
  - Workspace-SDC mode: task 018's submission rebuilt at 700 ps (published evaluation clock 900): working SDC,
    evaluation SDC and targets.json all at 700; the flow's synthesis read the new clock ("Setting clock period to 700",
    `abc … -D 700`); the flow's own finish WS (+53.763 ps) equals the measured wns at 700 (+53.763 ps); 114 s of flow.
  - Image-SDC mode: not exercised. Task 004's published submission is rejected by EDA-env's own sanitizer ("unknown
    variable SKIP_PRE_PLACE_REPAIR"), consistent with its reported gate 0. All 11 registered submissions were then
    checked locally with the same sanitizer code (whitelist, patch apply, config delta): all pass.
- **s04** (workflow run 41573930542, commit c57ff47), EDA-env rebuild in image-SDC mode: task 014's **starter**
  configuration (no submission; not registered) at 420 ps. The edited stock SDC was bind-mounted over the image's
  (image and task copies of that SDC have the same sha256, 992a8a76…); the flow's own finish WS (+5.66863 ps, working
  SDC) equals the measured wns at 420 (+5.668632 ps, evaluation SDC), so the flow saw the new clock. 537 s of flow
  (aes, NUM_CORES=8 on 4 vCPUs).

Code changed by the smoke runs (all before this registration): the EDA-env driver's two bugs above; a starter-config
option used only by s04; a diagnostic field (the flow's own WS) in flib. No change to the configurations, the judge,
the chain rule or the test.

## Budget
At most 2 jobs at once (this workstream's share). 14 configurations × (1 replay + ≤ 4 rebuilds) ≤ 70 flows; expected
35–45 flows, about 20–25 flow-hours (mult16/adder64/sboxpipe 2–5 min, aes 10–15 min, ibex 20–40 min, jpeg 45–90 min,
sky130hd aes 60–90 min per flow); the primary phase (28 flows) about 6–7 h of wall time, the chains after it.

## Caveats known in advance
1. ASAP7 is a predictive PDK, judged at one fast corner; sky130hd here at tt only. Not signoff.
2. The three ORFS-agent configurations are the best runs of the authors' published database, not the specific runs
   behind their paper's tables (whose knob values are unpublished).
3. Fourteen winners from two sources; eleven come from one agent (Kimi-k3 on EDA-env) and share designs (four aes).
   Not independent samples. Thirteen are ASAP7, one sky130hd.
4. The EDA-env rebuild changes the task's clock (working and evaluation SDC); absolute-ps knobs stay as published. A
   rebuild that also scaled those knobs would ask a different question.
5. The flows are deterministic in E5's image; EDA-env reports that its ECP moves with the thread count (2.7 % between 8
   and 16 threads on one task). NUM_CORES matches each publication (4 and 8).
