# Workstream B — launch record (docs/qa_week/B_PREREG.md)

Pre-registration: docs/qa_week/B_PREREG.md, hashed in farm/prereg_hashes.txt:
- original e813410515604e6f2d2517f9abaac1e6308c6876c5c87cd630a13860c9578d8f (commit 9e3c24f, hash commit cdadff9, 02:23Z)
- with Amendment B.1 3c633b31993b5b232f00ce1b4742e5c5de692fede60ca8d5d89c35bc185974b7 (commit 55429f5, hash commit 9c69316, 02:41Z)

Smoke (plumbing only, excluded from every analysis): sky130 run 41566723780 (batch s01), ASAP7 run 41566736833 (qa-b-asap7,
batch s01). Receipt: SMOKE_B.md (outbox) — controls bit-identical, frozen delays verified, resume stage verified.

| arm | branch | batch | code commit | dispatched (UTC) | workflow run | max-parallel |
|---|---|---|---|---|---|---|
| C0 | qa-b-frozen-io | (no runs) | c7298c3 (farm/qa/B/c0.py) | 2026-11-03 02:26Z (analysis) | — | — |
| C2a | qa-b-frozen-io | c2a1 (48 chains, 18 groups) | 9c69316 (farm/qa/B/run_group.py, blib.py, resume.py, b_farm.yml) | 2026-11-03T02:41Z | 41567699017 | 4 |
| C3 | qa-b-asap7 | g01 (30 grid runs, 6 groups; chains picked on the runner) | 5def9c4 (farm/qa/B3/, b_asap7.yml; E5's e5lib/e5_hook unchanged) | 2026-11-03T02:42Z | 41567743736 | 2 |

C1, S and C2b: not launched yet (they wait for free share; see docs/qa_week/B_PREREG.md and the workstream report).
