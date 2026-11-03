# Experiment E (reading the chip) — smoke receipt: one capture-enabled source run

Plumbing only; excluded from every analysis. 2026-11-03 02:19–02:22Z (Nov 2, 21:19–21:22 ET).

- **What ran:** workflow run 41565377087 (farm.yml dispatched on branch `qa-e-reading`, commit c99b6fb), 1 job,
  tag `smoke-ers-xtea-01` = an exact replay of the record's run `xab1-xtea-001` (xtea, a *training* design, asked
  16.72 ns, Addendum 35 search run), with the new `"capture": true` job-spec option of `br/run_job.py`.
  Toolchain as every farm run: LibreLane 3.0.16 image `ghcr.io/librelane/librelane@sha256:4bc9042b…7205051`,
  sky130A PDK 8afc8346, 4 vCPU GitHub runner. Flow 66 s; whole job 3 min 18 s.
- **Replay check:** all 293 keys of the final `metrics.json` are identical to the record's run (worst setup slack
  9.153121186730747 ns, register-to-register 12.496551 ns, worst hold 0.0985870302188283 ns, DRC 0, 360 std cells,
  wirelength 3,351 µm). Capturing changes nothing in the flow (it copies files after the flow has finished).
- **Captured (all gzipped, in the run's artifact `result-<tag>`, retention 30 days):** routed DEF (34 KB), mapped
  netlist (7.6 KB), signoff SDC, SPEF at the three RC corners min/nom/max (41–45 KB each), the post-route STA report
  tree (9 corners × checks/max/min/power/skew/tns/wns/ws/violator reports + summary), the post-global-route STA reports,
  plus what every farm run keeps: per-net dump after global route (`nets.jsonl.gz`), per-net dump at signoff
  (`nets_signoff.jsonl.gz`), net connectivity (`final_nets.json.gz`), per-net slew/cap/fanout violations
  (`labels.json`), 9 `checks.rpt`, metrics, resolved config, gzipped flow log.
- **Outcome:** smoke passed; no design change needed. The 35 registered source runs use the same option.

## Addendum (2026-11-03 04:15Z): packing, leak-test negative control, scorer/chain fixtures, runner-side chain smoke
Asked for by Codex's audit of this receipt. All plumbing; nothing here enters an analysis.
- **Packed views agree** (`farm/qa/E/verify_packets.py`, all 47 rung-2 packet views): the net-name sets of the
  post-GRT dump, the signoff dump, the connectivity file, the DEF NETS section and the SPEF D_NETs (through the name
  map) are identical after pseudonymization (supply nets aside; picorv32's 67 unconnected input-port nets carry no
  parasitics in the raw SPEF either); every connectivity instance is a DEF component; SPEF units are 1 NS / 1 PF /
  1 OHM, DEF 1000 units per µm; the dumps carry exactly the 9 STA corners; contract claim = target − metrics WS and
  R1 = ceil05(claim). Result: 0 problems.
- **Leak test negative control**: every run of `farm/qa/E/leak_test.py` first plants leaks in a copy of a real packet
  (the design name and an original port name inside the gzipped per-net dump, a `/work/` path inside a gzipped STA
  report, an unlisted file) and must catch every kind; it did (9 hits). Then all 82 packet views: 0 leaks.
- **Fixtures**: `farm/qa/E/fixtures/test_score.py` (source-only kept clock, null kept clock, first rebuild without
  metrics → fail with undefined slope, chain never landed → not checked, invalid prediction) and `test_chain.py`
  (runner-side chain on a fake deterministic flow incl. a no-metrics first rebuild; identical to the baselines' chain
  simulation) both pass.
- **Runner-side chain smoke**: workflow run 41575897220 (farm.yml on `qa-e-reading` at 7edebc5, 2 jobs, training
  designs only, 04:04–04:10Z). `smoke-erk-usb_cdc_core-01` (tight source x6d-usb_cdc_core-010, 7.80 ns, claim 8.328):
  R1 8.35 failed (claim 9.163), step back to 9.20 failed (claim 10.034), chain ended, kept clock none. 
  `smoke-erk-xtea-01` (passing source xab1-xtea-001, 16.72 ns, claim 7.567): 7.60 → 5.75 → 5.40 → 5.05 ns all passed,
  stopped at the 4-rebuild cap, kept 5.05 ns, slope 0.200. Both match the registered rule; artifacts < 1 MB each.
