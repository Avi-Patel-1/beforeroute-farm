# F log (times ET, 2026-11-02/03)

- 21:05 start. Research: ORFS-agent (paper + GitHub run database), AuDoPEDA, ResizerAgent (not found), EDA-env
  (ICCAD 2026 artifact on Zenodo), TicTacBench, others (see F_PREREG.md).
- 21:26 smoke s01 (41566134694): ORFS-agent harness reproduces a published database row bit-identically; EDA-env driver
  bug (case dir) fixed.
- 21:44 smoke s02 (41567954983): EDA-env replay path OK; rebuild-mode bug (SDC truncated before read) fixed;
  sky130hd ORFS-agent smoke cancelled after 51 min in detailed routing → ibex/sky130hd deferred before registration.
- 22:37 smoke s03 (41573339561): workspace-SDC rebuild path OK; image-SDC path blocked by task 004's own submission
  (rejected by EDA-env's sanitizer); all 11 registered submissions pass the sanitizer (checked locally).
- 22:44 smoke s04 (41573930542): image-SDC rebuild path OK (flow WS = measured wns at the new clock).
- 22:56 PREREG committed 3932f94 (code frozen); hash ba4d1510… in farm/prereg_hashes.txt (ae9fc3e).
- 22:57 registered batch r01 dispatched (f0c3667), workflow run 41575196054.
- 23:57–03:07 primaries landed for ee008, ee016, ee011, oa-aes-s130, oa-aes-a7, oa-ibex-a7, ee001.
- 03:05 **Infrastructure failure**: Zenodo returned HTTP 503 for the EDA-env archive (also from this machine).
  Group ee013 failed at the source fetch (5 attempts, no flow run). The six remaining EDA-env groups (ee097, ee054,
  ee074, ee087, ee037, ee075) would fail the same way, so run 41575196054 was cancelled at 03:12 with 7 primaries
  landed (artifacts f-r01-<group> kept). ee097 and ee054 were cancelled inside the fetch step, before any flow.
- **Deviation (infrastructure only; no change to configurations, harnesses, judge, chain rule or test):**
  1. fetch_sources.sh: if Zenodo is unavailable, the archive's content is taken from the authors' GitHub mirror
     (github.com/Ergodex-Labs/eda-env-iccad-26 @ 89dfcbed4376e2065b3917249f6c91f56dbf79bc) and accepted only if all
     1,295 files match a per-file sha256 manifest made from the sha256-pinned Zenodo archive
     (farm/qa/F/edaenv_manifest.sha256). The mirror at that commit is byte-identical to the archive (checked here:
     `diff -r` clean; manifest check passes). Tested: a tampered copy is rejected.
  2. f_field.yml: the continuation phase can continue a chain whose primary phase landed in an earlier run
     (`cont_only`, `primary_run_id`), so the seven landed groups are not rerun.
  3. Retry batch r01b, per the PREREG's infrastructure rule: the seven EDA-env groups whose flows never ran, with the
     same tags (ee013 is its one retry; the other six never started), then the chain continuations of all 14 groups.
- 03:16 Zenodo answering again (HTTP 200); the fallback stays as insurance.
- 03:22 retry batch r01b dispatched (2605db9), run 41602153382: the seven EDA-env primaries landed by 04:25 ET.
- 04:25 **registered verdict computed** (all 14 replays and first rebuilds landed): P2 holds (6/14 fail at R1), P1
  fails (median d1 −1.5 %) → the plan's prediction fails. F_RESULT.md (61b063c); independent audit
  (AUDIT_RESULT_F.md) confirmed the counts; wording fixed (e8d3fab).
- 05:52 **Bug in the continuation phase (descriptive chains only):** the ORFS-agent harness script wrote its outputs to
  results/<tag> (hard-coded) while the continuation phase reads and uploads results-cont/, so oa-aes-s130's step-back
  run at 4.05 ns (flow completed, docker rc 0, 26 min) left no readable result and its chain was ended as a failure
  (fail-closed, but wrong). oa-ibex-a7's and oa-aes-a7's continuations in r01b are affected the same way. EDA-env
  chains are not affected (their driver takes the results path), nor is any primary-phase result (which used
  results/). Fixed: the results directory is mounted explicitly (OUTROOT). The three ORFS-agent chains are continued
  again from their primary state in batch r01c (same tags) once r01b finishes (one workflow run at a time).
