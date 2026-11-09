# Workstream AD — D result: three nodes, one flow

Pre-registration: docs/qa_week/AD_PREREG.md with Amendment 1 (SHA-256 760b49c6…3869c; hash line 753295e in
farm/prereg_hashes.txt, branch qa-ad-law), written and hashed before any non-smoke run. Scored by the committed script
`python3 farm/qa/AD/ad.py analyze` (ad.py at fbed433, adlib.py at 286e4aa; no change since the T2 and T3 results);
numbers in farm/qa/AD/ad_analyze_d.json. Workflow run 41574461473 (batch m01) completed with success on
2026-11-03 17:47 UTC, before the registered hard stop (Nov 4 23:00 UTC). All 15 chains started and landed. The run was
collected and scored on 2026-11-09; nothing was re-run.

**Bottom line.** D1 held and D2 failed. In one OpenROAD flow and image, every one of the 15 new tuner winners failed
its first rebuild at the clock it claimed: 9 of 9 at 130 nm (sky130hd) and 6 of 6 at 2 nm (GT2N). With E5's 7 of 9 at
7 nm (ASAP7), that is 22 of 24 across three nodes. The size of the tight-side overclaim at 130 nm is LibreLane-sized,
not ASAP7-sized, which agrees with T2(a): the node sets it, not the flow.

## Verdicts
| | Registered | Outcome | Held? |
|---|---|---|---|
| D1 | At least 55% of the new winners (≥ 9 of 15) fail their first rebuild | **15 of 15 failed** | **yes** |
| D2 | sky130hd tight-bin median claim error nearer ASAP7's −5.6% than LibreLane's −14.5% (median > −10.05%) | **−12.2%** (22 runs) → nearer LibreLane | **no** |

## What was run (E5's protocol verbatim; times in ps)
Per design, three settings (S0 as shipped, S1 sparser floorplan, S2 denser placement) on a clock grid; the top three
per design by AutoTuner's score (claim, DRC-penalized) are the winners; each is rebuilt at ceil5(claim); one step back
after a failed first rebuild; at most four rebuilds; the kept clock is the last pass. Judge: post-route setup and
hold met at the platform's corner and detailed-route DRC 0. sky130hd: gcd, aes, ibex (9 winners). GT2N: gcd, aes
(6 winners; ibex does not fit the runner's memory).

## Every first rebuild
| chain | node | design | winner asked | winner's claim | rebuilt at | setup slack | hold slack | setup miss | limiting path | chain after | kept |
|---|---|---|---|---|---|---|---|---|---|---|---|
| adsk-gcd-1 | 130 nm | gcd | 1845 | 2325.0 | 2330 | −83.5 | +568.3 | 3.6% | port | 2415 fail | none |
| adsk-gcd-2 | 130 nm | gcd | 2240 | 2406.9 | 2410 | −64.9 | +568.7 | 2.7% | port | 2475 pass, 2455 fail | 2475 |
| adsk-gcd-3 | 130 nm | gcd | 2110 | 2407.1 | 2410 | −86.6 | +568.8 | 3.6% | port | 2500 pass, 2465 fail | 2500 |
| adsk-aes-1 | 130 nm | aes | 3350 | 3409.7 | 3410 | −82.4 | +453.9 | 2.4% | reg-to-reg | 3495 fail | none |
| adsk-aes-2 | 130 nm | aes | 3350 | 3536.2 | 3540 | −130.4 | +467.6 | 3.7% | reg-to-reg | 3675 fail | none |
| adsk-aes-3 | 130 nm | aes | 2935 | 3672.6 | 3675 | −126.7 | +469.5 | 3.4% | reg-to-reg | 3805 fail | none |
| adsk-ibex-1 | 130 nm | ibex | 7920 | 8494.0 | 8495 | −302.6 | +426.7 | 3.6% | port | 8800 fail | none |
| adsk-ibex-2 | 130 nm | ibex | 6525 | 8517.5 | 8520 | −337.2 | +420.3 | 4.0% | port | 8860 fail | none |
| adsk-ibex-3 | 130 nm | ibex | 7455 | 8561.5 | 8565 | −135.5 | +417.9 | 1.6% | reg-to-reg | 8705 fail | none |
| adgk-gcd-1 | 2 nm | gcd | 180 | 218.8 | 220 | −6.3 | +3.2 | 2.9% | port | 230 fail | none |
| adgk-gcd-2 | 2 nm | gcd | 210 | 219.8 | 220 | −8.6 | +4.5 | 3.9% | port | 230 pass | 230 |
| adgk-gcd-3 | 2 nm | gcd | 220 | 226.3 | 230 | −2.2 | +2.3 | 1.0% | port | 235 pass | 235 |
| adgk-aes-1 | 2 nm | aes | 365 | 405.3 | 410 | −41.5 | **−10.0** | 10.1% | reg-to-reg | 455 fail | none |
| adgk-aes-2 | 2 nm | aes | 415 | 408.6 | 410 | −7.9 | **−8.2** | 1.9% | reg-to-reg | 420 fail | none |
| adgk-aes-3 | 2 nm | aes | 440 | 439.2 | 440 (itself) | +0.8 | **−13.5** | met | reg-to-reg | 445 fail | none |

- **14 of the 15 missed setup at the claimed clock**, by 1.0 to 10.1% of the clock (130 nm: 1.6 to 4.0%, all nine on
  setup with hold met). The fifteenth, GT2N aes at 440 ps, is the winner itself (it met timing at its own target, so
  it is its own first rebuild): it meets setup by 0.8 ps and fails hold.
- **Only 4 of the 15 chains found a passing clock** within the registered single step back (gcd on both nodes). The
  other 11 end with no kept clock: one rebuild shows the claim is wrong, and one step back is often not enough to find
  what the setting can meet.
- sky130hd bins with the chains included (the registered D2 population, 50 runs): tight −12.2% (22), near +0.0% (15),
  loose +19.7% (11), very loose +30.4% (2).

## Descriptive: the T2(b) control (no criterion)
ASAP7 gcd and aes through Yosys/ABC *without* the clock target (`adc-*`, 20 runs): s⁻ 0.246 (7 runs), s⁺ 0.585 (6).
T2(b) with the target: 0.298 and 0.641. Per design, aes is 0.448 without the target (2 runs below F) and 0.472 with
it; under OpenROAD's `syn` in E5 it was 0.186. So most of aes's rise in T2(b) came from switching `syn` to Yosys,
not from telling ABC the clock. This supports T2(b)'s "not synthesis" reading; it rests on few runs (4 of 6 settings
have an interpolated F).

## Caveats
1. One corner per platform, no SDC margins. sky130hd: TT 25 °C 1.80 V. GT2N: the kit's single corner.
2. GT2N has 72 cells, no RCX rules in ORFS (post-route timing uses global-route parasitics), and its backside power
   grid is not built. GT2N aes missed hold at its own corner already in the pilots, so its three failures are not
   clean tests of the setup claim: two also miss setup, one misses only hold. Without GT2N aes, D1 is 12 of 12.
3. Three designs at 130 nm and two at 2 nm; three settings each. The winners are the tuner's top three by claim, which
   selects for pushed runs: 13 of the 15 winners had missed timing at their own target (claim above the ask).
4. The rebuild grid is 5 ps, which is 2.2% of a 220 ps clock at 2 nm. GT2N gcd-3 missed by 2.2 ps.
5. Scored six days after the runs landed, with the script as committed on Nov 3.

## Say it as
> "I repeated the 7 nm protocol at 130 nm and at 2 nm inside the same OpenROAD flow, with the prediction written down
> first: at least 55% of the tuner's top picks would fail at the clock they claim. Fifteen of fifteen failed. At
> 130 nm all nine missed setup, by 2 to 4% of the clock. With the 7 nm audit that is 22 of 24 across three nodes."

Do not say: "2 nm signoff" (one corner, 72 cells, global-route parasitics); "every tuner pick fails" (these are picks
ranked by claim, mostly from runs that missed timing; the published-winner test F found 6 of 14); "the same size at
every node" (D2 failed: at 130 nm the overclaim is larger than at 7 nm).
