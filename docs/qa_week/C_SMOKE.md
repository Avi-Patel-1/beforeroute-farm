# SMOKE_C — Experiment C ("method, not model"): plumbing smoke tests, Nov 3 2026, 02:48–03:05 UTC

These tests check plumbing only and are **excluded from every analysis**. The pre-registration
(docs/qa_week/C_PREREG.md, sha256 e28db918…, hash line 2026-11-03T02:47:43Z, branch qa-c-method commit fd53d9e) was
hashed before either farm smoke ran. Both smokes passed. **No design change was forced, so no amendment is needed.**
Nothing of the races has run.

Context for a reader new to the repo:
- The experiment reruns TrueClock's flow-tuning races (LibreLane/OpenROAD, sky130, signoff at 9 corners) with new
  "readers":
  - Opus with the timing reports deleted;
  - a 9-billion-parameter open model;
  - a four-line script.
- Each arm's best setting is then rebuilt at its claimed clock.
- Clocks are in ns. "Rule file" = the JSON policy that pins up to 8 of the 15 flow knobs before the Bayesian search
  (Optuna TPE) starts.

## 1. The open-weights rule-writer (arm m9) on a free GitHub-hosted runner

GitHub Actions run **41568345354** (workflow `c_m9.yml`, branch qa-c-method), batch `smoke-m9`, one call.
- Model: Qwen3.5-9B, Apache-2.0, Q4_K_M GGUF (lmstudio-community, pinned revision and sha256).
- Engine: llama.cpp b11700 (commit 23f7aab), built on the runner with fixed AVX2 flags.
- Decoding: greedy, thinking off, at most 2,048 reply tokens.
- Prompt: the exact 12,615-byte prompt Claude Opus 5.5 read for race xtea/seed 1 on Oct 30 (Addendum 35, arm g),
  reports included.

| step | measured |
|---|---|
| build llama-server (once; cached for tomorrow) | 241 s on an Intel Xeon Platinum 8370C runner; `version: 0.7.0-dev (build 1, commit 23f7aab)` |
| download the GGUF from Hugging Face | 5,627,044,256 bytes in 42.2 s (133 MB/s); sha256 verified in 4.1 s |
| runner for the call | AMD EPYC 7763, 4 vCPU, 15.6 GB RAM (AVX2 kernels; no AVX-512 used) |
| server start (model load) | 6.0 s |
| prompt processing | 4,713 tokens at 13.9 tokens/s (≈ 340 s) |
| reply generation | 301 tokens at 5.1 tokens/s (≈ 59 s); ended by itself (`stop`), no thinking text |
| call wall time | 398 s |
| whole call job | 7.6 min (checkout and cache 5 s, download and check 46 s, call step 405 s, upload 1 s) |
| **reply → rule file** | **parsed on the first try** by the Addendum 35 parser into a valid rule file. 7 pins (RC_MODEL orfs, density_delta 10, FP_CORE_UTIL 25, SYNTH_STRATEGY "AREA 3", SYNTH_SIZING true, PL/GRT setup margins 0.1). Nothing clamped or dropped; no re-ask needed. |

Notes:
- The smoke reply did **not** pin period_frac (the clock target).
- This is reported for completeness only. The smoke reply is not used, and tomorrow's race call for this race is made
  afresh. Every prediction (including "m9 pins period_frac ≤ 0.5 in 6–9 of 10") was hashed before this call.

**Projection for tomorrow's 10-call m9 batch** (prompts of 4,700–5,300 tokens; build cached):
- about 8–9 min per job, about 1.4 runner-hours in all;
- wall clock about one job's time if max_parallel ≥ 10, about 25 min at 4.

## 2. Farm dispatch from the experiment's branch: a replay of one start-set run

GitHub Actions run **41569619963** (`farm.yml --ref qa-c-method`, max_parallel 1), tag `smoke-c-xtea-003`.
- Spec = `x6z-xtea-003` (xtea, 13.12 ns target, one of the 8 shared start runs, run Oct 28) with only the tag changed.
- **Result: identical, 280 of 280 metric keys.**
  - Worst setup slack 6.648293 ns, worst hold slack 0.098828 ns, std-cell area 2,894.03 µm² (both runs);
  - flow 68.4 s; job 2 min 50 s (about 1.7 min of image pull and PDK-cache overhead).
- What it shows:
  - job specs committed on the branch run under `--ref qa-c-method`;
  - the artifact is named and downloaded as the race driver expects (`collect.download_artifact`);
  - **the farm reproduces an Oct 28 run bit for bit**, so comparing tomorrow's new arms with the Oct 28–30 arms
    (b, f, g, a) is sound.

## 3. Local tests (no farm time)

- **llama.cpp b11700 built locally** (527 s on 2 CPUs) and run end to end through `run_m9.py` with the 0.8B sibling
  model (Qwen3.5-0.8B; plumbing only, not an arm). The local test used a 300-token cap.
  - Model load took 8 s; it read the same 4,713-token prompt.
  - Every path ran: reply, parse failure, schema-constrained re-ask, empty-policy fallback, receipt.
  - Under greedy decoding the 0.8B fell into a repetition loop, which is why the registered re-ask constrains the
    reply's form.
  - The local build and model were deleted afterwards to free disk (coordinator's request).
- **Race driver dry run** (`tune_c.py --dry-run` with synthetic flow outcomes; nothing committed or dispatched):
  - both race sets ran end to end: 360 rule-race runs (240 round runs, 30 closures, 90 chain re-runs) and 84
    proposer runs;
  - proposer prompts for rounds 2–4 were written and leak-checked at writing;
  - the registered scoring computed every test;
  - an injected unreadable m9 reply fell back to the empty policy as registered;
  - the dry outputs were then deleted.
  - Separately, `--init --script --status` ran against the empty real state: 10 script rules, with 17 Opus calls and
    10 m9 calls shown as due.
- **Scoring self-test:** `c_score.py --selftest` recomputes all 12 counts of the A35/A32/A33 record from their states
  (g>b 9, g>f 4, f>g 4, h>g 4, a>b 6, a>f 3, …): 12 of 12 match.
- **Leak check:** 17 of 17 scores-only prompts PASS. Six planted leaks are all caught:
  - the original prompt;
  - a later run tag;
  - "fixed point" in the text;
  - a tampered score;
  - a re-added report line;
  - report words inside a setting line.
- **Reply saver:** `save_opus_reply.py` re-extracted an Oct 30 A35 Opus reply from its transcript byte for byte. It
  identified the model as `claude-opus-5-5`, confirmed the protocol (one Read, of its own prompt file) and the delivery
  note, and refused to overwrite.

## Files
- Branch qa-c-method: `farm/qa/C/m9/smoke/smoke-rule-xtea-s1/` (receipt, reply, download and build records) and
  `docs/qa_week/C_SMOKE.md` (this file).
- Artifacts (30 days): `c-m9-smoke-m9-smoke-rule-xtea-s1` (run 41568345354), `result-smoke-c-xtea-003`
  (run 41569619963).
