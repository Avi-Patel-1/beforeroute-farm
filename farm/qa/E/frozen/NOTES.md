# Rung 3 formula (frozen)

**Fields:** `contract.json` only (`metrics.json` as a fallback). From `source`: T0, worst setup slack, claim C0,
reg-to-reg WS, port_limited, hold WS, route DRC, DRV count, passes_judge. Also `judge.drv_bar`, `chain.R1_ns`,
`chain.max_rebuilds` and the io-delay percentage. No per-net dumps, `layout/` or `sta/`.

**Slope.** dT = R1 − T0, r = min(|dT|/C0, 0.3), relax = [dT > 0].
s = 0.713 − 0.255·relax − 2.147·r + 2.013·relax·r. When tightening, s is at least the fixed-netlist port slope
(max(T0 − r2rWS, C0 + 0.2·dT) − C0)/dT, which is 0 for reg-to-reg sources. If dT = 0, s = 0. The constants are a
family-weighted L1 fit on the 274 exact-R1 rows.

**p_pass.** C(T) = C0 + (s ± 0.10)·dT, using −0.10 when relaxing and +0.10 when tightening.
p_setup = logistic((T − C(T)) / (0.013·C0 + 0.05·|dT|)).
p_other = 0.995/(1 + e^{25(drv/bar − 0.97)}), times 0.88 if hold < 0 and 0.5 if DRC > 0.
p_pass = p_setup·p_other, clipped to [0.01, 0.99]. If R1 = T0 the rebuild is identical, so the source's own result
decides. Call: pass if p ≥ 0.6, fail if p ≤ 0.4, otherwise abstain.

**Kept clock.** The registered chain is simulated deterministically under the contract rule. A rebuild at T passes when
p_pass(T) ≥ 0.5 and claims C(T). The result is null when no simulated run passes.

**Leave-one-family-out (16 families, 274 exact-R1 rows):**
- Slope MAE: 0.442 per row, 0.489 per family. Median absolute error 0.271; MAE 0.381 where |dT| ≥ 0.1. A constant
  median gives 0.466 / 0.509.
- R1 pass: log-loss 0.37, Brier 0.113, accuracy 0.84. The baseline using only the source's pass/fail has Brier 0.134.
- Kept clock (in-sample, 170 chains emulated from the record): null status right in 148; MAE 0.30 ns where both are
  non-null.
