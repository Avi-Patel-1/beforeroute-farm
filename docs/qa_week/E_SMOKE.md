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
