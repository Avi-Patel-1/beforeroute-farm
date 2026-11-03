# Workstream B (constraint hygiene) — pre-registration: is it just your SDC? Freeze the I/O budgets and re-run the audit

Written 2026-11-03 02:30Z (`date -u`) by the workstream-B agent of the TrueClock overnight push, **before any run with
frozen I/O budgets** (smoke or otherwise) and before any non-smoke run of this workstream. Its SHA-256 is appended to
farm/prereg_hashes.txt on branch qa-b-frozen-io (pushed) before the first non-smoke dispatch. The experiment design and
every prediction below are copied from the plan Avi read (/home/claude/ideas/constraint-hygiene.md §3, written
2026-11-02); where the plan leaves a rule open, the choice made here is marked **[B's choice]**: made by the agent before
any outcome of that arm, not seen by Avi before launch. Plan tables (populations, F_best, D): farm/qa/B/plan.py →
farm/qa/B/plan.json (committed with this file). Code that runs the arms (farm/qa/B/ on qa-b-frozen-io; farm/qa/B3/ on
qa-b-asap7) is written after this file and smoke-tested before launch; the commit each arm launches from is appended to
farm/qa/B/LAUNCH.md before its first non-smoke dispatch. If a smoke test forces a change to anything below, an amendment
is appended to this file (and hashed) before launch. Results: docs/qa_week/B_RESULT_<arm>.md.

## Question
TrueClock's claim: a tuner's one-run *claimed clock* C = asked period T − worst setup slack is a guess, because a new
target builds a different circuit. Two mechanisms were named: (1) **bookkeeping**: every flow here budgets I/O delays as
a fixed fraction of the clock (LibreLane base.sdc: `CLOCK_PERIOD × IO_DELAY_CONSTRAINT/100`; ORFS ASAP7 SDCs:
`clk_period × clk_io_pct`), so a port path's slack moves 0.8 ns per ns of target; (2) **physics**: the tools build a
different circuit at a different target. The panel review's objection: "an SDC artifact presented as a discovery."
B asks: **with the I/O budget held fixed the way a PD engineer would hold it (to the product clock), does the one-run
claim still miss, and do tuned winners still fail when rebuilt at their claim?**

## The fix (the only change; everything else is the record's own job spec)
- **sky130 / LibreLane 3.0.16 (farm.yml image, unchanged).** Each design's I/O delay is held at
  **D = io0 × F_best** (ns), where F_best = the fastest clock the design has closed in the record and io0 = the design's
  shipped I/O fraction (0.20; the five clip16 designs ship 0.10 and keep it). One job override:
  **`IO_DELAY_CONSTRAINT = 100·D/T`** (percent, rounded to 6 decimals; written as the integer 100·io0 when T = F_best).
  base.sdc then sets input and output delay = T × (100·D/T)/100 = D at every target T. Clock uncertainty (0.25 ns),
  derate (±5%), driving cell and load are untouched.
- **F_best rule [B's choice of the exact filter; the plan says "the fastest clock it has closed in the record"]:** the
  smallest CLOCK_PERIOD among full-flow runs of designs/<design> in /home/claude/eda/results (as of this registration)
  that completed with metrics and met setup and hold at all nine corners (`timing__setup__ws` ≥ 0,
  `timing__hold__ws` ≥ 0) with `route__drc_errors` = 0. (The slew/cap bar is not part of F_best: it only sets D.)
  Values (plan.json `fbest`; the plan's approximate "XTEA ≈0.85, bm64 2.25 ns" correspond to 0.840 and 2.280):

| design | F_best (ns) | set by | io0 | D (ns) | | design | F_best | set by | io0 | D |
|---|---|---|---|---|---|---|---|---|---|---|
| xtea | 4.20 | xac-xtea-024 | 0.2 | 0.840 | | APU | 8.70 | x8k-APU-003 | 0.2 | 1.740 |
| cic_decimator | 3.90 | xac-cic_decimator-011 | 0.2 | 0.780 | | PPU | 13.20 | x8k-PPU-004 | 0.2 | 2.640 |
| zipdiv | 5.60 | xac-zipdiv-023 | 0.2 | 1.120 | | chacha | 17.65 | x7k-chacha-002 | 0.2 | 3.530 |
| usb_cdc_core | 5.55 | xac-usb_cdc_core-015 | 0.2 | 1.110 | | salsa20 | 18.55 | x7k-salsa20-004 | 0.2 | 3.710 |
| wbqspiflash | 6.45 | xac-wbqspiflash-013 | 0.2 | 1.290 | | sha512 | 30.06 | x4w-sha512-008 | 0.2 | 6.012 |
| aes_cipher | 10.30 | x7k-aes_cipher-003 | 0.2 | 2.060 | | clip16_h0 | 4.00 | x7k-clip16_h0-001 | 0.1 | 0.400 |
| picorv32 | 9.30 | x7k-picorv32-004 | 0.2 | 1.860 | | clip16_h1 | 4.35 | x7k-clip16_h1-001 | 0.1 | 0.435 |
| y_huff | 7.01 | x4l-y_huff-004 | 0.2 | 1.402 | | clip16_native | 5.92 | x5w-clip16_native-014 | 0.1 | 0.592 |
| des | 8.25 | x7k-des-004 | 0.2 | 1.650 | | clip16_packedclip | 4.65 | x7k-clip16_packedclip-003 | 0.1 | 0.465 |
| md5 | 15.50 | qe1-md5-1550 | 0.2 | 3.100 | | clip16_stickyround | 4.25 | x5c-clip16_stickyround-001 | 0.1 | 0.425 |
| bm64 | 11.40 | x7k-bm64-005 | 0.2 | 2.280 | | | | | | |
| ocs_blitter | 11.00 | x7k-ocs_blitter-010 | 0.2 | 2.200 | | | | | | |
| blabla | 21.90 | x7k-blabla-003 | 0.2 | 4.380 | | | | | | |

- **ASAP7 / ORFS (E5's pinned image and machinery, branch qa-e5-asap7 → qa-b-asap7).** One regex on the design's own
  constraint.sdc, applied after AutoTuner's `set clk_period` substitution: **`set clk_io_pct 0.2` → `set clk_io_pct
  <0.2·P0/T>`** (8 significant digits), P0 = the design's ORFS default period (gcd 310, aes 380, ibex 900 ps), so the
  I/O delay is 0.2·P0 = 62, 76, 180 ps at every target. At T = P0 the file is left byte-identical. The virtual I/O
  clock's fixed latency is untouched.
- **Control (bit for bit).** At T = F_best (ASAP7: T = P0) the override reproduces the stock configuration exactly, so
  the run must equal the stock record run in every metric. Registered control checks: (i) smoke: replay xac-xtea-024
  (XTEA at F_best = 4.20 ns) with the override → `metrics.json` identical to the record's in every key (E4's E4a test);
  (ii) the 7 C1 replays that sit exactly at their design's F_best (APU 8.70, PPU 13.20, bm64 11.40 ×2, chacha 17.65,
  clip16_packedclip 4.65, ocs_blitter 11.00) must each equal their source run; (iii) C3's three S0 runs at P0 (tags
  b3g-<design>-003) must equal E5's e5g-<design>-003 in every metric of the merged logs/*.json except execution-time
  keys (names containing `runtime` or ending in `_s`; E5's own replays differ only in those). A failed control stops the arm: no number
  from it is reported as a result until the cause is found and an amendment is hashed.

## Definitions (shared)
- **Claim** C = T − worst setup slack (sky130: `timing__setup__ws`, worst over 9 corners incl. port paths; ASAP7:
  `finish__timing__setup__ws`) — exactly what AutoTuner ranks. **Register claim** C_r = T − register-to-register worst
  slack (`timing__setup_r2r__ws`; ASAP7: E5's hook value). **Port-limited**: worst slack below the register-to-register
  worst slack (sky130 tolerance 1e-4 ns as in agents/analysis/fixedpoint/analyze.py; ASAP7 0.006 ps as in e5lib).
- **Judge, sky130** (as the record): flow completed with metrics; setup WS ≥ 0 and hold WS ≥ 0 (worst over the nine
  corners); `route__drc_errors` = 0; max-slew + max-cap violation count (nine corners) ≤ the design's stock reference
  (the count the original study used: A24/A25 designs: x1d-/x2d-<design>-001; race designs: Addendum 30's stock run,
  farm/tune_a32.py `ref_drv_x8`; values in plan.json `c2a[*].drv_ref`). A run with no metrics after one
  infrastructure retry fails. **Judge, ASAP7**: E5's (e5lib.load_run: setup ≥ 0, hold ≥ 0 at ORFS's ASAP7 corner,
  detailed-route DRC 0).
- **Rebuild chain** (the brief's rule; E5's e5lib.chain_next with the grid 0.05 ns on sky130 = farm/tune_a32.py
  `ceil05`, 5 ps on ASAP7): chain[0] = the winner run W (target T0, claim C0). (1) First rebuild at R1 = ceil(C0); if W
  passed and R1 ≥ T0, W is its own first rebuild. (2) After a passing rebuild with claim C: rebuild at ceil(C) while that
  is below the chain's smallest passing clock and above every failed clock of the chain below it. (3) If the first rebuild
  fails: step back once to max(ceil(C1), R1 + one grid step), unless that is not below the chain's smallest passing clock;
  a failure after that ends the chain. (4) At most 4 new runs per chain. **Kept clock** K = the chain's smallest passing
  clock. **First rebuild fails** = R1 fails the judge. **Rebuild-again gain** g = T1/K, T1 = the chain's first passing
  rebuild clock (slide 5's definition, E2_RESULT.md). A rebuild target already run in the same chain reuses that result.
  Every rebuild carries the frozen budget of its own target (sky130 IO_DELAY_CONSTRAINT = 100·D/R; ASAP7 0.2·P0/R).
- **Fixed point** F of a setting: agents/analysis/fixedpoint/analyze.py `crossing` of C(T) = T (one point per target,
  the median claim if repeated); "bracketed" = `interpolated` (a missed target below a met one). **Claim error**
  e = (C − F)/F per run; bins by T/F: tight < 0.9, near 0.9–1.1, loose 1.1–1.5, very loose > 1.5.
- **Slope** of a setting: least-squares slope of C against T (port: over its port-limited runs, ≥ 2 distinct targets;
  register: of C_r against T over all its runs, for settings with no port-limited run) — analyze.py's `slope_port` and
  `slope_r2r`. Record values (60 bracketed settings): port 0.36 (n 26), register 0.36 (n 26).

## Arms, predictions (verbatim from the plan) and pass/fail tests
### C0 — register-to-register score of the existing audit (registered analysis, no runs). Script farm/qa/B/c0.py
- Data: agents/analysis/fixedpoint/data.json `groups` (139 settings with runs at ≥ 2 targets, built Oct 29). Per
  setting: F_r = `crossing` of the register claim C_r(T) = T; settings whose F_r is bracketed enter; e_r = (C_r − F_r)/F_r
  at each of their runs, binned by T/F_r.
- **Prediction: tight median beyond −10%.** Test: median e_r over the tight bin < −0.10 → PASS.
- **Seen before registration (disclosed):** the plan's own pass ("tight-target runs still overclaim a median 15.2%
  (104 runs, 89 beyond 5%, worst 50%)") used this definition; B reproduced it before writing this file (55 settings
  bracketed, n 104, median −15.15%) and also saw the restriction to the 60 all-path-bracketed settings (48 bracketed, n
  84, median −14.7%). The plan's "55 of 60 settings" is 55 of the 139. C0 is therefore a registered reproduction with a
  committed script, not a blind test. The 60-setting restriction is reported beside with the same threshold.
- Meaning: PASS = even the maintainers' proposed metric (ORFS #4583: period − reg2reg worst slack) overclaims tight
  targets, so removing ports from the *score* does not remove the error. FAIL = the error lives in the port paths.

### C1 — audit replay with frozen budgets (≈400 runs, ≈110 flow-h). Scripts farm/qa/B/c1_*.py
- Population (plan.json `c1`): the 60 settings whose all-path fixed point is bracketed in the record, one replay per
  distinct target: **328 runs**, each = its record job spec + the override (tags b1r-<design>-<nnn>). 7 of them sit at
  their design's F_best (control ii).
- **Top-ups (≤ 2 per setting) [B's choice of the rule]:** after a setting's replays land, if its frozen fixed point is
  not bracketed: met at every target → next target 0.95 × min(F_x, T_min); missed at every target → 1.05 × max(F_x,
  T_max); neither ("fit all") → 0.95 × min(F_x, T_min); F_x = `crossing`'s estimate (T_min/T_max when None); targets
  rounded to 0.01 ns; the second top-up repeats the rule on the updated points (tags b1t-<design>-<nnn>).
- **Prediction: port slope of claim vs target < 0.15 (was 0.36), register slope ≥ 0.25; tight median still beyond
  −8% (expect −12±4%), ≥60% of tight runs beyond −5%, n ≥ 60; loose ≥ +5%.** On the settings bracketed with frozen
  budgets:
  - C1a: median port slope < 0.15. C1b: median register slope ≥ 0.25.
  - **C1c (headline): tight-bin median e < −0.08 AND ≥ 60% of tight-bin runs have e < −0.05, with n_tight ≥ 60**
    (n_tight < 60 → "insufficient", not PASS). Point prediction −12% (−8 to −16%).
  - C1d: loose-bin median e ≥ +0.05.
- Meaning: C1c PASS = with honest budgets a one-run claim still overclaims a tight target (physics). C1c FAIL inside
  −5% = most of the sky130 tight-target drift was the constraint convention (plan §4).

### C2a — the 48 winners replayed at their search target with frozen budgets, then chained (≈290 runs, ≈35 flow-h)
- Population (plan.json `c2a`): the 8 Bayesian-tuned winners of Addenda 24/25 (each design's best feasible TPE run:
  x1t-aes_cipher-017, x1t-picorv32-014, x1t-y_huff-005, x2t-des-008, x2t-md5-012, x2t-bm64-007,
  x2t-ocs_blitter-022, x2t-blabla-021) and the 40 race winners of Addendum 35 (each race arm's best feasible run,
  farm/tune_a35.py `arm_best`; 5 designs × 2 seeds × arms b/f/g/h). In the record, 4 of the 48 first rebuilds failed
  (picorv32, y_huff, bm64 and the cic_decimator f1 winner); the "3 original failures" are picorv32, y_huff, bm64.
- Per winner: W = its job spec replayed at its own search target T0 with IO_DELAY_CONSTRAINT = 100·D/T0 (tag
  b2a-<design>-<nn>-0), then the chain above (tags b2a-<design>-<nn>-<k>). Runner-side: one job per chain group.
- **Prediction: ≥2 of the 3 original failures still fail (all three physics: two port-limited whose arithmetic
  predicted a pass, bm64 register-limited); ≥2 of 48 fail; rebuild-again median ≥ 1.05×.**
  - C2a-i: ≥ 2 of {picorv32, y_huff, bm64} have a failing first rebuild.
  - C2a-ii: ≥ 2 of the 48 first rebuilds fail.
  - C2a-iii: median g over chains with a passing rebuild ≥ 1.05.
  A winner whose replay has no claim (flow error after the retry) leaves the denominators and is reported.
- Meaning: C2a-i/ii PASS = winners still fail at their claim with frozen budgets ("a measured no" to "it's just your
  SDC"); FAIL (≤ 1 fails) = the rebuild failures were mostly the convention. C2a-iii PASS = rebuilding again still pays.

### C2b — fresh TPE 8+8 with frozen budgets, 5 race designs × 2 seeds, winners rebuilt (≈200 runs, ≈15 flow-h)
- Per race (design d, seed s ∈ {1, 2}): an Optuna TPE study configured exactly as Addendum 35's plain arm b
  (farm/tune_a35.py `study(d, "b", s, {})`, seed `seed35(d, s)`, same knob space, constraint function and objective),
  warm-started with Addendum 30's 8 start-set settings each re-run at its own target with frozen budgets (8 runs), then
  8 TPE runs (4 rounds of 2) with frozen budgets. Winner = best feasible claim among the 8 TPE runs (A35 `arm_best`),
  rebuilt with the chain above. Tags b2b-<design>-s<seed>-<nnn>.
- **Prediction: ≥1 of 10 fails its first rebuild; ≥6 of 10 gain >2%.** C2b-i: ≥ 1 of the 10 winners' first rebuilds
  fails. C2b-ii: ≥ 6 of 10 chains have g ≥ 1.02 (slide 5's ">2%" is computed as ≥ 1.02, E2_RESULT.md; a chain with no
  passing rebuild does not gain).

### C3 — ASAP7: the E5 grid with frozen budgets, AutoTuner's score picks the top 3, chains (≈65 runs, ≈15 flow-h)
- The E5 grid unchanged (qa-e5-asap7 farm/qa/E5/grid.json: per design S0 as shipped at {0.70, 0.85, 1.00, 1.40}·P0,
  S1 sparser floorplan and S2 denser placement at {0.80, 1.20, 1.45}·P0; 30 runs; tags b3g-<design>-<nnn> numbered as
  E5's e5g), every run with clk_io_pct = 0.2·P0/T. On the runner, once a design's 10 runs have landed: top 3 by
  AutoTuner's `calculate_score` (e5lib.tuner_score; ties by tag), each chained by E5's rule with frozen budgets (tags
  b3k-<design>-<rank>-<k>). ibex runs unconditionally (it met E5's 60-minute rule).
- **Prediction: gcd's picks hold within 2% or turn register-limited; aes ≥2 of 3 still fail; ibex within 1%.**
  - C3-gcd: each of gcd's 3 picks has |K/C0 − 1| ≤ 0.02, or its first rebuild is register-limited (not port-limited).
  - C3-aes: ≥ 2 of aes's 3 picks fail their first rebuild.
  - C3-ibex: each of ibex's 3 picks has |K/C0 − 1| ≤ 0.01.
  (K = kept clock; a chain with no passing clock does not "hold".) Reported beside: d1 = C1/C0 − 1 per pick, the
  limiting path per run, the S1/S2-style claim-error bins with frozen budgets.
- Meaning: gcd's E5 failures were I/O bookkeeping (E5's own split: 96–126% of each move), so they should vanish;
  aes's were register-to-register physics, so they should stay.

### S — sensitivity: D = 1.0 ns flat for the 40 race winners, first rebuild only (≈80 runs, ≈5 flow-h)
- The 40 race winners as in C2a with D = 1.0 ns for every design (IO_DELAY_CONSTRAINT = 100/T): replay at T0
  (tag bs-<design>-<nn>-0) and the first rebuild at ceil05 of that claim (tag bs-<design>-<nn>-1).
- **Prediction: same verdicts as C2a.** [B's choice of the reading:] S-a (registered): the C2a-ii test applied to these
  40 winners ("≥ 2 first rebuilds fail") gives the same verdict under D = 1.0 ns as under C2a's D. S-b (strict reading,
  reported beside, no criterion): the 40 per-winner first-rebuild verdicts all agree.

## Decision times and handling
- C2a-i/ii and C3's first-rebuild tests are computed when all their first rebuilds have landed; C2a-iii and the C3 kept
  clocks when every chain has ended; C1 when all replays and top-ups have landed; C2b, S when their runs have landed.
  Latest decision for every arm: **Sat Nov 7 23:00 UTC** on what has landed then (anything missing counts as not
  checked, and the result says so). C2b and S are dropped first if the farm is contended; a dropped arm is reported as
  not run, never as a result.
- Infrastructure failures (runner lost, image pull, job timeout, missing artifact): re-dispatched once with the same
  tags. A flow error the retry reproduces is a result (a winner without metrics is never rebuilt; a rebuild without
  metrics fails the judge). Runner-side chains that hit the per-job time budget stop between flows and are continued
  by the same workflow run's resume stage with no change of rule.
- Smoke runs (tags `smoke-`) test plumbing only and enter no analysis. Nothing in the populations, the fix, the
  judge, the chain rule or the tests changes after this file is hashed; any deviation is logged in the result file.
- Farm: at most 6 of this workstream's jobs running or queued at once across both branches (one active workflow run
  per branch, max-parallel summing to ≤ 6).

## Caveats known in advance
1. **D is a choice.** F_best is the minimum over many record runs (an optimistic product clock), so D is small and
   loose targets get a small I/O fraction (C1: 4–31% of T, median 12.8%). S (D = 1.0 ns flat) and C0 (no I/O at all)
   bound it. The ASAP7 rule uses ORFS's default period P0, not a record F_best, as the plan specifies.
2. **Frozen budgets make loose-target port claims tighter**, so some claim errors change sign; compare claims within an
   arm only.
3. **Selection under the old SDC.** The 48 winners and the 60 settings were picked by searches under scaling budgets;
   C2b is the arm whose search itself runs with frozen budgets.
4. **The slew/cap reference** comes from stock runs with stock budgets (I/O delays barely touch slew/cap).
5. **Not independent samples:** 48 winners from 13 designs (40 from 5); 60 settings from 21 designs; ASAP7: 3 designs.
6. **C0 was seen before registration** (above). C1–C3, S, C2b: no frozen-budget run of any kind existed when this was
   written.
7. Synthesis: LibreLane's ABC sees the clock target (`-D`), not the I/O delays; ORFS's synthesis sees neither (E5).

## Amendment B.1 (2026-11-03, before any non-smoke run; clarifications and launch facts — no population, rule, judge, test or prediction changed)
1. **Erratum.** The header's "02:30Z" should read 02:22Z: the file was committed (9e3c24f) and its hash pushed (cdadff9)
   at 02:23Z.
2. **Chain cap.** "(4) At most 4 new runs per chain" counts rebuilds after W. In C2a and S, W's frozen replay at its
   search target is the arm's step 0 and is not one of the 4 (as in E5, where W was a grid run; the brief's "≤ 4
   rebuilds").
3. **Runner staging (plumbing, no rule change).** sky130 chains run on the runner (farm/qa/B/run_group.py, blib.py;
   .github/workflows/b_farm.yml), one flow at a time per job, each flow exactly as farm.yml runs a job (br/run_job.py,
   same image and PDK; the opt-in `skip_dumps` key only skips the post-flow per-net dumps). A job starts no new flow after
   15,000 s (job timeout 300 min); a chain left incomplete is continued by the same workflow run's resume stage
   (farm/qa/B/resume.py) with the same rule. The 8 Bayesian C2a chains stop after their first passing rebuild in stage 1,
   so that every first-rebuild verdict lands early, and continue in the resume stage. A flow without metrics is retried
   once with the same tag, as registered.
4. **Smoke outcomes seen before launch** (plumbing only, excluded from every analysis; receipt SMOKE_B.md):
   sky130 control smoke-b-xtea-ctl (xac-xtea-024 replayed at F_best = 4.20 ns with IO_DELAY_CONSTRAINT = 20) identical to
   the record in all 281 metrics; frozen runs show input and output delay 0.84 ns in the resolved config and in base.sdc's
   own log lines; ASAP7 control smoke-b3g-gcd-003 (310 ps = P0) identical to E5's e5g-gcd-003 in all 470 non-execution
   metrics; smoke-b3g-gcd-001 (215 ps) carries `set clk_io_pct 0.28837209` (62.0 ps). Outcome values also seen: the XTEA
   race winner xah1-xtea-007 replayed with frozen I/O at 11.71 ns claimed 4.51 ns (record, stock budget: 6.01 ns) and its
   first rebuild at 4.55 ns passed; gcd at 215 ps claimed 346.2 ps (E5, stock budget: 326.4 ps). No prediction changed.
5. **Scoring scripts:** farm/qa/B/c2a.py (C2a; reads the chain states collected by farm/qa/B/collect.py, which keeps only
   the members the analysis needs) and farm/qa/B3/c3.py on qa-b-asap7 (C3). C1, C2b and S scripts are written before
   their launch and named in farm/qa/B/LAUNCH.md.
6. **Farm share at launch:** C2a max-parallel 4 (qa-b-frozen-io), C3 max-parallel 2 (qa-b-asap7); C1, S and C2b wait for
   free share (one active workflow run per branch, ≤ 6 jobs in all).
