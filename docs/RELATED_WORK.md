# Related work and how BeforeRoute differs

**Closest prior work.** Chhabria, Jiang, Sapatnekar and Kahng, *A Machine Learning Approach to
Improving Timing Consistency between Global Route and Detailed Route*, ACM TODAES 2023
(arXiv 2305.06917). They train XGBoost regressors on post-global-route features (HPWL, sink
count, driving-point slew, congestion, guide-derived R/C) to predict post-detailed-route wire
delay/slew and parasitics, annotate the predictions into a modified OpenSTA, and let the
post-GR *timing* optimizer work on the corrected view. Result: post-DR worst slack improves on
13/15 OpenROAD designs (up to 0.24 ns).

BeforeRoute asks the complementary question and uses a different mechanism:

| | Chhabria et al. 2023 | BeforeRoute |
|---|---|---|
| Target | post-DR wire delay / slew / parasitics (regression) → setup WS | nets that fail **max-slew / max-cap / max-fanout at extracted nine-corner signoff** (classification) |
| How the prediction acts | annotated into the timer (modified OpenSTA source) | **do-not-touch mask** on the stock `repair_design`; no tool modification, works in any flow with dont-touch |
| Operating point | implicit (optimizer decides) | explicit budget k (nets flagged) and margin H; tiered margins |
| Evaluation | WS before/after on the same designs | leave-one-design-out model, arms from an identical checkpoint, **Pareto of violations vs cells changed / hold margin** |
| Training data | generated per design family | the flow's own signoff reports from past runs ("learns from signoff") |

**Other prior work.**
* Barboza, Shukla, Chen, Kahng, *Machine Learning-Based Pre-Routing Timing Prediction with
  Reduced Pessimism*, DAC 2019 — predicts post-route path timing from pre-route data; analysis,
  not an actuator.
* Castro Castro and Carvajal Barboza, *Hybrid ML for Lightweight Pre-Route Delay Estimation in
  Open-Source IC Design*, arXiv 2608.17914 (2026) — decision tree + linear leaves predicting
  segment delays in OpenLane/sky130; assistive, does not drive optimization.
* Xie et al., *RouteNet: Routability prediction for mixed-size designs using CNNs*, ICCAD 2018 —
  predicts routing DRC hotspots (shorts/spacing), a different problem from electrical DRVs.

**Tools and methods cited in the deck.** LibreLane 3.0.16 (OpenROAD, Yosys, KLayout, Magic,
Netgen); OpenROAD `rsz::repair_design` (slew/cap/fanout repair with `-slew_margin` /
`-cap_margin`) and `set_dont_touch`; SkyWater sky130A PDK, `sky130_fd_sc_hd`; LightGBM (Ke et
al., NeurIPS 2017); SHAP (Lundberg and Lee, NeurIPS 2017); designs: PicoRV32 (Claire Xenia Wolf, YosysHQ),
AES core (Rudolf Usselmann, OpenCores), and the LibreLane/OpenLane example designs.
