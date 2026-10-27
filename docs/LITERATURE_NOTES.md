# What the field already learned, and what BeforeRoute borrows (2026-10-26, 20:30 EDT)

Scope: ML/AI for physical design that touches our problem — predicting end-of-flow outcomes from
early stages and acting on them. Primary sources read where reachable; secondary summaries noted.

## NVIDIA's own EDA research (the audience's home turf)

| work | what it does | lesson for BeforeRoute |
|---|---|---|
| **GOALPlace** (Liang, Agnesina, Ren et al., ISPD 2025) | Guides global placement with per-cell *post-route* density targets taken from one end-of-flow run of a commercial tool; James-Stein shrinkage adapts targets to what the placer can reach; timing-critical cells protected explicitly. Up to 10× fewer DRCs, up to 5% wirelength; targets learned per design, no transfer shown; "predict post-route density without running the tool" is their stated future work. | Same philosophy ("begin with the end in mind"). We are the predictive version for electrical signoff: a model that transfers to unseen designs (LODO) instead of a per-design end-of-flow run. Borrow: *protect timing-critical cells explicitly* (we measured why: the hold-fix delay cells) and *shrink targets toward what the actuator can achieve* (our margin H and budget k play that role). |
| **INSTA** (Lu et al., DAC 2025, best paper) | Differentiable statistical STA on GPU, full-chip timing propagation in under a second; the gradient (`netGrad`) ranks nets by timing impact. | Their net selection is sensitivity of a *pre-route timing model*; ours is a learned prediction of *post-extraction electrical failure* the timing model cannot see. Complementary, and a natural combination: use INSTA-style gradients as features. |
| **LEGO-Size** (Lu et al., ISPD 2025) | Differentiable, signoff-accurate gate sizing with LLM assistance for advanced nodes. | "Signoff-accurate" is the bar they set for optimization: optimize against the signoff view, not the estimate. Our result restates the same gap for DRVs in an open flow and closes it with a learned proxy instead of a differentiable signoff timer. |
| **BUFFALO** (Hsiao, Lu, Lim, Ren, ICCAD 2025; GT PDF) | T5 generates buffer trees as bracketed token sequences; fine-tuned on >20M synthetic nets labelled by a commercial buffer engine; GRPO reward = ΔTNS (INSTA) vs ΔArea with tunable weights; chip-level stage optimizes only INSTA-selected high-impact nets; up to ~71% TNS vs commercial, ~83× faster per net; mixed per-design results; reward proxy validated on one net. | Two borrowings: (1) a **configurable benefit/cost trade-off** (their w1/w2 ≈ our k/H Pareto); (2) **select, then act on a subset** is how NVIDIA frames it too. Also a caution they state themselves: per-design variance and proxy validation — report per-design, which we do. |
| **ICCAD 2025 CAD Contest Problem C** (NVIDIA) | Incremental placement optimization beyond detailed placement: joint gate sizing, buffering, relocation. **2024 Problem C**: scalable gate sizing with ML + GPU. | The community benchmark for exactly our actuator class (sizing + buffering after placement). Worth naming in the deck as where a BeforeRoute-style selector would plug in. |
| **Hybrid RL for PD parameter tuning** (TODAES 2025); **ChipNeMo / ChipAlign / VerilogCoder / RTLFixer** | Flow-parameter tuning and LLMs for RTL/chat. | Different layer of the stack; cite for context only. |
| **OpenROAD + CircuitOps** (VTS 2024) | Open infrastructure and IR tables for ML-EDA research on OpenROAD. | Our per-net dump (`br/dump_nets.py`) is a CircuitOps-style table at the post-GRT point; say so, and note it could be re-expressed in their schema. |

## Closest academic prior work

| work | what it does | lesson |
|---|---|---|
| **Chhabria, Jiang, Sapatnekar, Kahng** (TODAES 2023) | XGBoost predicts post-DR wire delay/slew/parasitics from post-GR features; predictions annotated into a modified OpenSTA; post-GR timing optimizer then improves post-DR WS on 13/15 designs. | The direct ancestor. Differences: our target is multi-corner electrical signoff (classification), our actuator is a do-not-touch mask on the stock repair (no tool modification), our evaluation is leave-one-design-out plus arms from one checkpoint with cost/hold reported. |
| **AdaTimer** (CUHK, DAC 2024) "Disentangle, Align and Generalize" | Cross-design generalization of pre-route timing predictors by separating design-specific from invariant structure. | Generalization to unseen designs is the known failure mode of this family. We measure it directly (LODO over 10 designs) and keep features scale-free (ratios to limits, guide lengths, densities). |
| **Barboza et al.** (DAC 2019) pre-routing timing prediction with reduced pessimism; **PowPrediCT** (DAC 2024) cross-stage power prediction | Cross-stage prediction as a theme. | Same theme; none act through the repair step. |
| **RouteNet / DRC hotspot CNNs** (ICCAD 2018 onward) | Routing-DRC hotspot prediction from placement images. | Different problem (geometric DRCs). Cite for contrast. |
| **VeoPlace** (Harvard/DeepMind, arXiv 2603.28733, 2026) | A vision-language model reads a rendered chip canvas and proposes macro placements in language; training-free; improves analytical/RL placers up to ~4%, wirelength up to 32% on benchmarks. | Shows the "model proposes, tool executes/verifies" pattern NVIDIA and academia now favour; our separation (model flags, stock resizer acts, signoff judges, equivalence proves) is the same pattern one level down. |
| **Meta-Harness** (Lee et al., 2026) | Outer-loop optimization of harness code from full execution traces. | Our policy log follows it: candidates proposed from raw traces, evaluated on held-out designs. |

## Concrete things we adopt tonight

1. **Strongest frozen comparator** (from the review and from BUFFALO's baseline discipline): the AI ablation arm `det050-70` (rule R8 = worst of the three estimated ratios) at the same budget and margin.
2. **Report per design, never pooled** (GOALPlace/BUFFALO both show per-design variance); H1 tables are per held-out design, H2 per base.
3. **Signal nets only** for every ranking comparison — the clock-net violators had inflated the "estimate needs 44%" number; corrected in the pre-registration addendum.
4. **Protect what the actuator damages** (GOALPlace's timing-critical protection): we tried blanket protection (fails) and now report the hold cost as an explicit axis instead of hiding it.
5. **Position the claim precisely**: not "AI beats EDA", but "a learned, calibrated signoff proxy lets the *stock* repair act selectively; measured on unseen designs with the strongest hand rule as the ablation."

## Deck citations (works-cited slide)

Chhabria et al. 2023 (TODAES); Liang et al. GOALPlace (ISPD 2025); Lu et al. INSTA (DAC 2025) and LEGO-Size (ISPD 2025); Hsiao et al. BUFFALO (ICCAD 2025); Lee et al. Meta-Harness (2026); Ke et al. LightGBM (NeurIPS 2017); Lundberg & Lee SHAP (NeurIPS 2017); LibreLane / OpenROAD / Yosys / sky130 PDK; design sources (PicoRV32 — C. Wolf; AES — R. Usselmann; others per their repositories).

Sources: [NVIDIA EDA publications](https://research.nvidia.com/labs/electronic-design-automation/publication/), [GOALPlace arXiv](https://arxiv.org/html/2407.04579v1), [BUFFALO PDF (GT)](https://gtcad.gatech.edu/www/papers/Hsiao-ICCAD25.pdf), [INSTA PDF](https://research.nvidia.com/labs/electronic-design-automation/papers/yichen_INSTA_dac25.pdf), [LEGO-Size (ACM DL)](https://dl.acm.org/doi/10.1145/3698364.3705351), [VeoPlace (Kempner)](https://kempnerinstitute.harvard.edu/news/rethinking-chip-design-with-ai-that-can-see/), [AdaTimer (DAC 2024)](http://www.cse.cuhk.edu.hk/~byu/papers/C225-DAC2024-AdaTimer.pdf), [Chhabria et al.](https://arxiv.org/pdf/2305.06917), [Meta-Harness](https://arxiv.org/abs/2603.28052).
