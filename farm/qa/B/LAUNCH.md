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

## Fixes (dated; outcome-neutral)
- **2026-11-03 ~04:50Z — fail-closed judge (Codex code audit).** farm/qa/B/blib.py `load_run` read missing max-slew /
  max-cap counts as 0 and passed a run whose slew/cap reference was unknown, and did not check the job record. Fixed:
  a run is judged only if its job record says the flow completed and setup WS, hold WS, route DRC and both slew/cap
  counts are present and finite and the reference is known; otherwise it is not admitted and fails (the registered
  rule: a run without metrics fails). farm/qa/B/c2a.py now re-judges every chain entry from its own collected run
  directory with the fixed function and reports any entry where that differs from the flag the runner recorded.
  Before/after on everything landed at the time (C2a: 4 chains, 10 run directories; C3: 15 grid runs, judged by E5's
  e5lib.load_run, which already required a completed status and setup/hold/DRC): 10 of 10 C2a runs admitted, 0
  entries changed, C2a-i PASS (2 of 3) and C2a-ii PASS (2 of 4 landed) unchanged; C3 15 of 15 status "completed",
  no verdict yet. The C2a workflow run (41567699017, commit c4f055f) keeps stepping its chains with the old function on
  the runner; the re-judge in c2a.py catches any divergence. Later launches use the fixed function.
- **Provenance of c2a.py.** The C2a-i/ii verdicts logged at 23:37 ET were produced by c2a.py at commit 117e483
  (sha256 8897fa72…); outbox/code/B/MANIFEST.txt still listed the 3dba6ea version (647e1fbb…) because the file was
  re-copied without regenerating the manifest. The registered-test code is the same in both (117e483 added only the
  setup-only sensitivity). The manifest is now generated from git (path, commit, sha256) and checked after copying.
- **2026-11-03 ~08:45Z — trajectory check (Codex audit of LAUNCH/c2a/blib).** c2a.py also replays the registered
  chain rule over the fail-closed re-judged entries and compares each target with the one the runner ran. On all 48
  chains landed by then (stage 1 complete): 0 changed verdicts, 0 trajectory differences, so the pre-fix runner judge
  did not alter any chain. Every C2a run directory had all judged fields (194 of 194 admitted).

## C1 on lane 1 (qa-b-frozen-io, after C2a's run 41567699017 completed at 11:08Z)
- Lane 2 (qa-b-asap7) runs C1 chunk A: run 41593980763 (commit 689217c), see that branch's LAUNCH.md.
- **C1 chunk B** (batch c1b: 19 settings, 113 replays, 19 jobs, max-parallel 4), code at b6b2cbb (run_group.py, fail-closed blib.py, resume.py top-ups; scoring c1.py). Dispatched 2026-11-03T11:09Z.
- Workflow run **41625206127** (commit f3bea82), started 11:09Z with 4 jobs; C2a's run 41567699017 had finished at 11:06Z (success).
