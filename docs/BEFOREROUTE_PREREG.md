# BeforeRoute — pre-registered analysis plan

Written 2026-10-26 ~16:00 EDT, after the exploratory PicoRV32 sweep (`picorv32-base-v1`)
and before any result of the confirmatory sweeps (dispatched 19:45 UTC the same day:
GitHub Actions runs 40389515577, 40389526479, 40389536393) had been seen.
Everything below is fixed; anything added later is labelled *post hoc*.

## Claim

A per-net model trained on the flow's own post-global-route view predicts which nets will
violate max-slew / max-cap / max-fanout at extracted nine-corner signoff, and spending the
stock OpenROAD `repair_design` margins only on those nets removes most signoff violations
at a fraction of the collateral cost (cells changed, hold margin consumed) of applying the
same margins to every net.

## Toolchain (frozen)

LibreLane 3.0.16 image `sha256:4bc9042b…` (OpenROAD dcf36133a, Yosys 0.62), sky130A /
sky130_fd_sc_hd, ciel PDK `8afc8346…`. All runs on 4-vCPU GitHub runners or the dev
workspace; baseline re-runs from a checkpoint reproduce metrics exactly (verified on spm,
PicoRV32).

## Hypotheses and pre-fixed tests

### H1 — prediction (the blind spot is learnable and transfers across designs)

* Unit: a signal net at the post-GRT point of the baseline flow (stock margins 20/20 at
  post-GPL repair, no post-GRT repair). Label: net has ≥1 max-slew / max-cap / max-fanout
  violation in any of the nine `stapostpnr` corners after RCX extraction.
* Features: only quantities available at the post-GRT point (timer estimates, GRT guide
  lengths, HPWL, density, fanout, driver class, design knobs). No signoff information.
* Model: LightGBM binary classifier, fixed hyper-parameters (`br/train.py::fit`).
* Evaluation: leave-one-design-out — the held-out design contributes **no** rows to
  training. Primary metric: fraction of nets that must be flagged to catch 95% of
  violating nets (`frac_to_catch_95`), compared with the same quantity for the timer's own
  estimated worst-load slew ratio (the flow's built-in ranking). Secondary: PR-AUC,
  recall at 5% flagged.
* Success criterion: on every held-out design with ≥50 violating nets, the model needs
  fewer flagged nets than the timer estimate to reach 95% recall.
* Designs: PicoRV32, AES-128 cipher, CRC pipeline, SPM (data sweep d1/d2) plus eight
  ported designs (sha512, salsa20, y_huff, ldpcenc, des, bm64, ocs_blitter, md5; sweep
  d3/d4) as additional held-out folds as their runs complete.

### H2 — intervention (targeted repair dominates uniform repair)

* All arms resume from the same post-GRT checkpoint of a baseline run and run an
  identical downstream flow (DRT → RCX → nine-corner signoff). Arms:
  * `rerun`: control, no post-GRT repair (must equal the baseline exactly).
  * `uni<H>`: stock `OpenROAD.RepairDesignPostGRT` on every net, slew/cap margin H%.
  * `tgt<k>-<H>`: same step, margins applied only to the top-k% nets ranked by a model
    that never saw the base design (do-not-touch mask on the rest).
  * `tier<k1>-<H1>_<k2>-<H2>`: two tiers of margins (exploratory, labelled as such).
* **Fixed operating point** (chosen on `picorv32-base-v1` with the 3-run v1 model, before
  the confirmatory bases were run): k = 5%, H = 70%. The primary comparison is
  `tgt050-70` vs `uni70` (same margins) and vs `uni50` (similar number of cells changed).
* Outcome metrics, all from the final signoff of each arm:
  1. signal nets violating at signoff (primary); slew / cap / fanout breakdown;
  2. cost: standard-cell instances changed (`RSZ-0038/0039` resizes + buffers from the
     repair log), standard-cell area delta, **hold worst slack** (collateral of resizing
     hold-fix delay cells), setup worst slack, DRT runtime;
  3. clock-net violations are reported separately (neither arm touches clock nets).
* Success criterion: on each confirmatory base, `tgt050-70` removes ≥80% of the baseline's
  signal-net signoff violations while changing fewer cells and keeping more hold margin
  than `uni70`; residual violations are reported, never hidden.
* Confirmatory bases (dispatched 19:45 UTC): `d1-aes_cipher-000` with
  `models/model_holdout_aes_v2.txt` (trained on the 24 non-AES runs), `d1-picorv32-016`
  and `d1-picorv32-006` with `models/model_holdout_picorv32_v2.txt` (trained on the 24
  non-PicoRV32 runs). Arms per base: rerun, uni30, uni50, uni70, tgt030-70, tgt050-70,
  tgt050-80, tier020-80_050-50.

## What is exploratory (and will be labelled so)

* The `picorv32-base-v1` sweep (uni10/30/50/70, tgt020/050/100-70, tgt050-90) was used to
  pick k and H. It is reported as the exploratory sweep, not as a confirmation.
* Tiered margins; the `clkdlybuf4s25` exclusion experiment (negative result, kept).
* Any arm or design added after 2026-10-26 16:00 EDT.

## Rules

* No result is dropped. Failed or crashed arms are reported with their failure mode.
* The model used for a base never saw that base's design (not just that run).
* Numbers in the deck come from `results/<base>/hero_summary.json` files produced by
  `farm/hero_collect.py`, and from `results/model/report.json` produced by `br/train.py`.

---

## Addendum 1 — Round 3, prospective test on new design families (fixed 2026-10-26 20:25 EDT, before dispatch)

Prompted by an external review (Codex, 19:50 EDT) that correctly noted: the probability-threshold
budget was chosen after inspecting AES outcomes, and the comparator in H1 was too weak.

**Correction to H1 reporting.** The "estimate needs 44% of nets to catch 95%" figure for PicoRV32
counted clock-net violators (fanout/cap violations on clock buffers, which the slew ranking can
never reach). On *signal nets only* — the population the intervention acts on — the timer's
estimated slew ratio is a strong ranking (catch-95 at 3.5–8.8% of nets on 8 of 11 designs).
From here on, H1 is reported on signal nets against the strongest frozen deterministic rule:
**R8 = max(estimated load-slew ratio, estimated driver-slew ratio, estimated cap ratio)**,
chosen on all current development data as the most robust hand rule (mean catch-95 8.0%, median
6.7%, recall at 5% flagged 67–100%, mean 81%), plus a logistic-regression baseline. The blind spot
is therefore primarily a *calibration* failure of the estimate (violators sit at 0.8–1.0× the
limit before routing and 1.1–1.5× after extraction), not purely a ranking failure; the model's
measured contribution is a better ranking **and** a calibrated budget.

**Bases (outcomes never inspected; baselines ran in sweep d3 and were used only for violator
counts and as held-out LODO folds):** `d3-salsa20-000`, `d3-des-000`, `d3-y_huff-000`,
`d3-ocs_blitter-000`, `d3-bm64-000`, `d3-md5-000` — six design families absent from Rounds 0–2.

**Models:** one per base, trained on every run of every *other* design (`models/model_holdout_<design>_v4.txt`, dataset of 127 runs as of 20:20 EDT).

**Arms (all from the base's post-GRT checkpoint, identical suffix):** `rerun`, `uni50`, `uni70`,
`tgt050-70` (model, top 5%, H = 70), `thr500-70` (model, p ≥ 0.5, H = 70), `det050-70`
(rule R8, top 5%, H = 70 — the AI ablation: same budget and margin, no learned component).

**Primary outcomes:** signal nets violating at nine-corner signoff; cells changed (resizes +
buffers from the repair log); hold worst slack; std-cell area; setup worst slack; residual
breakdown (slew / cap / fanout-with-diodes).

**Pre-specified criteria:**
1. Targeting beats blanket repair: on ≥ 5 of 6 bases, `tgt050-70` removes at least as large a
   fraction of violators as `uni50` with ≤ 60% of its cells changed and ≥ its hold worst slack.
2. The learned ranking adds value over the best hand rule: on ≥ 5 of 6 bases, `tgt050-70` leaves
   fewer violators than `det050-70` at equal k and H (cells changed and hold reported alongside;
   if the rule arm matches the model arm, the deck credits the rule and the claim becomes
   "selective aggressive repair works; the model mainly supplies the budget").
3. The threshold budget generalizes: `thr500-70` removes ≥ 90% of violators on ≥ 4 of 6 bases;
   its hold cost is reported, not excused.

Anything not listed above is exploratory. No arm will be re-run with changed k, H or threshold.

