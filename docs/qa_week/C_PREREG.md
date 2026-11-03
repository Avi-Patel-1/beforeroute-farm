# Experiment C — pre-registration: method, not model. Who wrote the rule: the model, the reports, or one line?

Written 2026-11-03T02:47Z (`date -u`; the hash line in farm/prereg_hashes.txt on branch qa-c-method is authoritative) by
workstream C1 of the TrueClock overnight push (a Claude Opus 5.5 agent), under Avi Patel's green light for the overnight
package. **Avi did not see this file, its prompts or any choice in it before launch.** Written before any reply of the new
arms and before any race run (tags `xm*`, `xn*`); the m9 smoke call runs after the hash. One plumbing test ran before
this file was written: g's xtea s1 prompt was sent, on the agent's own machine, to the 0.8-billion-parameter sibling
model (Qwen3.5-0.8B, unsloth Q4_K_M GGUF, 300-token cap) to test the scripts; that model is not an arm, and its output was
used for nothing else. The lens that designed this experiment, `/home/claude/ideas/method-not-model.md`,
calls the two parts A37 and A38; they are renamed here because Addenda 37 and 38 are already E1 and E4 (docs/qa_week/).
Code frozen at commit `e7bd1c82d73d956beda4e5b0f4dc5ad1cb7d2603` (branch qa-c-method): `farm/qa/C/{clib.py, make_prompts.py,
leakcheck.py, c_score.py, tune_c.py, save_opus_reply.py, m9/config.json, m9/run_m9.py}`, `.github/workflows/c_m9.yml`,
`farm/jobs/smoke-c-xtea-003.json`, and the 17 prompt files listed in
`farm/qa/C/prompts/MANIFEST.json` (sha256 per file). Result: docs/qa_week/C_RESULT.md.

## Question
In every registered head-to-head so far, Claude Opus 5.5 helped TPE (Optuna's Bayesian optimizer) only as much as Avi's
one-line habit "pin the clock target at the floor of the space" (period_frac 0.45):

| record | comparison (fixed-point clocks, 2% rule) | result |
|---|---|---|
| A35 (10 races) | g (Claude's frozen rule from the start runs' reports) vs b (plain TPE) | 9 wins, 1 loss |
| A35 | g vs f (TPE with Avi's hand pin 0.45) | 4 wins, 4 losses, 2 ties |
| A36z | y (Avi's pin, zero search) vs b | 8 of 10 |
| A32 (7 designs) | a (Claude proposing settings from the reports) vs b | 6 of 7 |
| A33b | a vs f | 3 of 7 (FAIL; ≥ 4 needed) |

So how much of "the AI's" edge is the reports it reads, how much the model, and how much a rule a script could write?
Experiment C reruns the same races with four new readers on identical starts, seeds, budgets and judge:
- **s**: Opus 5.5 writing A35's rule from the same prompt **with the timing reports deleted** (scores only);
- **m9**: an open-weights 9-billion-parameter model (Qwen3.5-9B, Apache-2.0) writing the rule from **g's exact prompt**,
  run with llama.cpp on a free GitHub-hosted runner (4 vCPU, 16 GB, no GPU);
- **c**: a **four-line deterministic script** (pin 0.45 plus three knobs of the best start run; it reads scores only);
- **S**: Opus 5.5 **proposing settings** as A32's arm a did, from scores-only prompts.

## Toolchain (frozen)
- Flow runs: the farm as in Addenda 32–36, unchanged: `.github/workflows/farm.yml` (LibreLane image
  `ghcr.io/librelane/librelane@sha256:4bc9042ba177f73f275b5b39e7d372a07d3f4043f548a0ba7f640097b7205051`, sky130 PDK
  `8afc8346a57fe1ab7934ba5a6056ea8b43078e71`, one flow per GitHub-hosted 4-vCPU runner, `br/run_job.py --jobs 4`),
  dispatched from branch qa-c-method (`gh workflow run farm.yml --ref qa-c-method`). Job specs are written by the A27/A35
  code (`farm/tune_a27.py` write_spec, knob space `farm/tune.py` + RC model of `farm/tune_a25.py`).
- Search: Optuna 5.0.0 (the environment that ran A32–A36), the TPE sampler of Addenda 24–35 (multivariate, grouped,
  constant liar, constraint-aware), `farm/tune_a35.py` study/warm/ask_round/tell/closure_jobs/fixed_point and
  `farm/tune_a32.py` start_set/run_line/clamp/chain_next/fixed_point/wins, imported unchanged by `farm/qa/C/tune_c.py`.
- m9: `farm/qa/C/m9/config.json` pins everything that decides a reply:
  - model file `lmstudio-community/Qwen3.5-9B-GGUF` at revision `1379f25c6b505a3fc737bd7818cb09389cf807c1`,
    `Qwen3.5-9B-Q4_K_M.gguf`, 5,627,044,256 bytes, sha256 `cd76ec205963b3b33350093e6904d9de16c4e666fd104e1f632d25c7f15f2a13`
    (quantized from `Qwen/Qwen3.5-9B@c202236235762e1c871ad0ccb60c8ee5ba337b9a`, Apache-2.0). Chosen because its embedded
    chat template equals Qwen's official template byte for byte (checked through the Hugging Face GGUF metadata); the
    unsloth GGUF alters the thinking switch.
  - llama.cpp tag b11700, commit `23f7aabc16c72f6f707dba227251c35d7bd1ed96` (2026-10-16), built on the runner from source
    with fixed flags (AVX2/FMA/F16C/BMI2 on, AVX-512 off, no `-march=native`) so every runner CPU uses the same kernels;
    `llama-server -t 4 -tb 4 -c 16384 -np 1 --jinja --reasoning off`.
  - request: one user message = the prompt file's bytes; no system message; temperature 0, top_k 1, top_p 1, min_p 0,
    no repetition/presence/frequency penalty, seed 0, at most 2,048 reply tokens, `enable_thinking: false`.
  - workflow `.github/workflows/c_m9.yml` (runs when `farm/qa/C/m9/dispatch.json` changes on qa-c-method): a build job
    (cached by commit and flags), then one job per call: download the GGUF from Hugging Face and check its sha256, run
    `farm/qa/C/m9/run_m9.py`, upload the reply, the parsed rule file and a receipt (timings, tokens/s, CPU model).
- Opus calls: Claude Opus 5.5 (`claude-opus-5-5`), each a fresh sub-agent of the coordinator session told only the path
  of its prompt file, exactly as Amendment 35.1 (A35) and Addendum 32 delivered theirs. The delivery notes are A35's and
  A32's verbatim with the path changed (MANIFEST.json `delivery_note`). Each reply is saved unedited to the hand-off path
  `/home/claude/ideas/overnight/method/opus_replies/<race>/<call>.json`, with its model id and tool calls logged (as
  `agents/a35/audit.jsonl` did); `tune_c.py` copies it into `farm/qa/C/replies/` and commits it with the job specs that
  use it, before dispatch. An instance that reads any other file or uses any other tool is a logged protocol deviation
  (its reply is still used), as in Amendment 35.1.

## Definitions (unchanged from Addenda 32, 33, 35 and Amendment 32.2)
- T_eff = asked clock − worst setup slack over the 9 signoff corners (ns). Feasible = hold ≥ 0 at all 9 corners, router
  DRC 0, slew + cap violation pins (LibreLane's worst-corner aggregates, Erratum 35.E2) no more than the design's stock run.
- Constraint values TPE is told: [router DRC errors, −(worst hold slack), slew/cap pins − bar]; feasible iff all ≤ 0. A run
  without metrics is told T_eff = 2 × the design's default clock and [1000, 1000, 1000].
- Closure and chain (Addendum 31, Amendments 32.1/32.2): the arm's best feasible new run is re-run at ceil(T_eff/0.05)·0.05
  ns, up to 2 refinements after a miss; after a pass, re-run at the passing run's own ceil(T_eff/0.05)·0.05 while that is
  lower and no failed clock lies in between; at most 4 re-runs in the chain (closure included). **Fixed-point clock** = the
  smallest passing clock in that chain; "lower bound" = the largest failed closure clock when none passed.
- **x beats y** (Addenda 33/35, `tune_a32.wins`): x's fixed point is checked and ≤ 0.98 × y's (y checked or a lower bound),
  or y's arm has no feasible run. Anything not checked by the decision time is no win.
- **Tie within ±2** (the plan's "ties"): |wins(x over y) − wins(y over x)| ≤ 2 over the races compared.

## The races (reused unchanged) and the reused arms (no new runs)
**Rule races (lens A37)** = Addendum 35's 10 races: xtea, cic_decimator, zipdiv, usb_cdc_core, wbqspiflash × TPE seeds 1
and 2 (seed = 3500 + 1000·seed + crc32(design) mod 100000). Start set = the 8 live borrowed runs of Addendum 30 on the
design, told to each arm's study as its first 8 trials. Budget per arm and race: 8 new runs (4 rounds × 2), then closure
and chain. A rule = a policy pinning up to 8 of the 15 knobs; TPE chooses the rest (Optuna PartialFixedSampler).
**Proposer races (lens A38)** = Addendum 32's 7 held-out designs (xtea, zipdiv, usb_cdc_core, wbqspiflash, cic_decimator,
APU, PPU), the same 8 start runs each, 8 new runs (4 rounds × 2 settings), closure and chain.

Reused fixed-point clocks (ns; read from `results/tune_xa/state.json` and `results/tune_x8/state.json` by `c_score.py`,
identical to the decision records 35.D and A32/A33):

| rule race | b | f | g |  | proposer design | a | b | f |
|---|---|---|---|---|---|---|---|---|
| xtea s1 | 5.05 | 4.60 | 4.65 | | xtea | 4.45 | 4.55 | 4.45 |
| xtea s2 | 4.50 | 4.95 | 4.25 | | zipdiv | 5.70 | 7.40 | 6.20 |
| cic_decimator s1 | 4.70 | 4.40 | 4.00 | | usb_cdc_core | 5.85 | 6.10 | 5.75 |
| cic_decimator s2 | 4.60 | 4.00 | 4.10 | | wbqspiflash | 6.65 | 7.65 | 7.95 |
| zipdiv s1 | 6.55 | 5.65 | 6.10 | | cic_decimator | 4.00 | 4.60 | 4.00 |
| zipdiv s2 | 6.50 | 6.75 | 5.95 | | APU | 8.70 | ≥ 9.45 (lower bound) | 9.05 |
| usb_cdc_core s1 | 5.85 | 5.70 | 5.60 | | PPU | ≥ 13.45 (lower bound) | 13.20 | ≥ 13.45 (lower bound) |
| usb_cdc_core s2 | 7.35 | 5.55 | 5.90 | | | | | |
| wbqspiflash s1 | 7.25 | 6.45 | 7.60 | | | | | |
| wbqspiflash s2 | 7.90 | 8.10 | 7.70 | | | | | |

`c_score.py --selftest` recomputes from those states, with the code used below, every count the record states: g>b 9,
b>g 1, g>f 4, f>g 4, h>g 4, g>h 2, h>f 5, f>h 3, f>b 7 (A35); a>b 6 (A32a3), f>b 5 (A33a), a>f 3 (A33b). All 12 match.

## The new arms
### Rule races: one frozen policy per race, then exactly arm g's search (tags `xm<arm><seed>-<design>-<nnn>`)
Each new arm writes one policy per race before round 1 and keeps it for all 4 rounds (as g). The policy goes through
`tune_a35.parse_policy` exactly as g's did (first `{` to last `}`, JSON; unknown knobs dropped; values clamped to the
space; pins beyond 8 dropped; all logged). TPE then searches with the race's seed and the policy's pins; closure and chain
as above. Closure tags `xmk-`, chain tags `xmc-`.
- **s — scores-only Opus 5.5** (10 calls, one fresh instance per race as g had). Prompt = g's round-1 prompt for that race
  (regenerated by `tune_a35.prompt_text`; equal to the committed `farm/agent_a35/<design>/s<seed>/round1_prompt.md` byte
  for byte) passed through the scores-only transform below. Files `farm/qa/C/prompts/rule-<design>-s<seed>/round1.md`
  (copies in the hand-off folder `opus_prompts/`).
- **m9 — Qwen3.5-9B on a GitHub-hosted runner** (tag letter `m`; 10 runner jobs, one per race). Prompt = **g's prompt file
  bytes unchanged** (the reports included). Decoding and versions as pinned above. The two seeds of a design receive the
  same prompt; under greedy decoding their replies are expected to be identical (reported as a replay check).
- **c — the four-line script** (tag letter `d`, because `c` and `k` are the chain and closure letters of this code; no
  model call). `clib.script_pins`: pin period_frac 0.45 and copy SYNTH_STRATEGY, RC_MODEL and FP_CORE_UTIL from the start
  run with the lowest T_eff among the feasible ones (ties: first in start order). It reads only scores (T_eff and
  feasibility). Its rules, fixed by the start set before any new run:

  | design | pins (both seeds) |
  |---|---|
  | xtea | period_frac 0.45, SYNTH_STRATEGY "DELAY 3", RC_MODEL orfs, FP_CORE_UTIL 21 |
  | cic_decimator | period_frac 0.45, SYNTH_STRATEGY "AREA 3", RC_MODEL cap213, FP_CORE_UTIL 30 |
  | zipdiv | period_frac 0.45, SYNTH_STRATEGY "AREA 3", RC_MODEL cap213, FP_CORE_UTIL 40 |
  | usb_cdc_core | period_frac 0.45, SYNTH_STRATEGY "AREA 3", RC_MODEL cap213, FP_CORE_UTIL 30 |
  | wbqspiflash | period_frac 0.45, SYNTH_STRATEGY "DELAY 4", RC_MODEL cap213, FP_CORE_UTIL 27 |

**Unreadable reply (the lens's rule):** one re-ask, then the empty policy {} (= plain TPE), logged. For s the re-ask is the
same prompt to a fresh instance. For m9, greedy decoding would repeat the same reply, so its one re-ask (made inside the
same runner job) is the same prompt with the output constrained to the reply's JSON form (`{"rationale": string, "pins":
object}`, llama.cpp `response_format` json_schema).

### Proposer races: arm S (tag letter `p`; tags `xnp-<design>-<nnn>`, closure `xnk-`, chain `xnc-`)
Each round a fresh Opus 5.5 instance reads the scores-only version of the prompt A32's arm a would have received with S's
own history (`tune_a32.PROMPT`/`run_line` text with S's runs and its own earlier rationales, then the same transform), and
replies with a rationale and exactly 2 settings of all 15 knobs in JSON. Values are clamped and missing knobs filled
exactly as A32 (`tune_a32.clamp`; logged). Round 1's 7 prompts are written and hashed now (`prop-<design>/round1.md`);
rounds 2–4 are written by `tune_c.py --prop-prompts` when S's previous round on that design has landed, leak-checked at
writing (the report-bearing original is committed beside it as `round<k>.full.md`), and committed before the reply is
requested. Unreadable reply: one re-ask (same prompt, fresh instance, as A32); if that is unreadable too, S makes no more
runs on that design and the design is unresolved for S (no win either way), logged.

### The scores-only transform (`clib.scores_only`; s and S)
Applied to the full prompt text, it (1) deletes every signoff-report line (lines beginning `  setup: `, `  hold: `,
`  electrical: `, `  cells: `, `  routing: `, `  clock: `, `  run stopped before signoff`); (2) inserts after each run's
setting line one line with the three constraint values TPE is told (for a run without a result: "no result" and the
values TPE is told); (3) rewords three sentences that point at the reports: "Each run shows its setting and a signoff
summary." → "Each run shows its setting and its scores (T_eff and the three constraint values the optimizer sees).";
"using what the signoff summaries tell you (for example which corner limits setup, …, wire length against the pre-route
estimate)" → "using what the scores tell you"; "what the reports suggest" → "what the scores suggest". Nothing else
changes. The reader keeps: the task, the GOAL paragraph with its re-run framing, the design's name, function, default
clock, stock cell count and bar, the knob space, and per run its setting, clock target, T_eff, FEASIBLE/INFEASIBLE with
the reason, and the constraint values (S also its own earlier rationales). It loses, per run: the corner that limits
setup, reg-to-reg vs port-limited, TNS and violating endpoints, hold slack and its corner, hold buffers, slew/cap per
corner, fanout, cell and repair-buffer counts, area, utilisation, wirelength vs the pre-route estimate, detailed-route DRC
by iteration, clock skew, power, runtime and the last error of a failed run. The 10 rule prompts lose 38–48 report lines
each; the 7 proposer round-1 prompts likewise.

**Leak check** (`farm/qa/C/leakcheck.py`, must PASS before any prompt is handed over; it does, 17 of 17): for each prompt
P and the full original O, (1) every HISTORY line is a run head line, a setting line, a score line in the fixed template,
or S's own rationale; (2) no report line and no report vocabulary; (3) every line of P is in O, in O after the three
edits, or a score line; (4) each score line's numbers equal what TPE is told about that run; (5) no run tag O does not
show, no tag pattern of any later run (A35/A36/A32 arms, closures, chains, this experiment's own runs other than S's own
history), no outcome file names or result words. Negative controls (the original prompt, an injected later tag, an
injected "fixed point", a tampered score, a re-added report line, report words inside a setting line) are all caught.
**Design names stay in the prompts on purpose**: g's and a's prompts had them, so removing them would change two things at
once. This departs from the overnight brief's rule 10 (no design names in a blind reader's packet); the reason is that s
and S are ablations of g and a, not outcome readers, and Opus 5.5's training cutoff (June 2026) predates every A30–A36
run, so a name carries no outcome. Flagged for the coordinator.

## Budgets (equal to the originals)
- Per rule race and new arm: 8 new runs + closure (≤ 3) + chain (≤ 4 re-runs in all), as g (A35: g used 114 runs, 5.3
  flow-hours over 10 races). Three new arms: ≈ 340 runs, ≈ 16 flow-hours.
- Per proposer design: 8 new runs + closure + chain, as a (A32: a used 78 runs, 13.7 flow-hours; PPU runs take 38–87
  min). Arm S: ≈ 80 runs, ≈ 14 flow-hours.
- Model calls: s 10 (as g), m9 10 runner jobs, c 0, S 28 (as a: 7 designs × 4 rounds), plus at most one re-ask each.
- A run stopped by infrastructure (no job.json after its farm run) is re-sent, at most twice; a third loss counts as a
  failed run (logged). A run the flow itself stops counts as used (A32).

## Registered tests (computed by `farm/qa/C/c_score.py`, which imports the A32/A35 fixed-point and win code unchanged)
| ID (lens) | test | pass if |
|---|---|---|
| **C-R1** (A37-1) | g beats s | g wins ≥ 5 of the 10 races and loses ≤ 2 |
| **C-R2** (A37-2) | m9 beats b | m9 wins ≥ 5 and loses ≤ 2 |
| **C-R3** (A37-4) | c beats b | c wins ≥ 5 and loses ≤ 2 |
| **C-P1** (A38-1) | a beats S | a wins on ≥ 4 of the 7 designs |
| **C-P2** (A38-2) | S beats b | S wins on ≥ 4 of the 7 designs |

Not registered here (not in this workstream's task; only a new pre-registration can add them): the lens's A37-3 (m120,
gpt-oss-120b, and o, GPT-5.3 or Gemini 3 Pro), its optional arm k (Avi's own rules) and its optional replication R.

## Predictions (from the plan, quoted verbatim; not the writer's)
The coordinator's task, from the lens: **"the script and the small model tie Opus within ±2 races; reports buy the
proposer 2–3 of 7 designs."**
The lens (method-not-model.md §3), verbatim: "**A37-1** g beats s: *fails* (within ±2; s pins period_frac ≤0.5 in ≥7/10,
taught by the prompt's re-run framing). **A37-2** m9 beats b: *passes* 6–8/0–2; m9 pins ≤0.5 in 6–9/10; ties g. […]
**A37-4** c beats b 7–9/10, ties g." and "**A38-1** a beats S on ≥4 of 7: *fails* (a ahead on 2–3: zipdiv and wbqspiflash,
where it beat f by 8.8% and 19.5%); **A38-2** S beats b on ≥4 of 7: *passes* narrowly".

How `c_score.py` scores each prediction as held (operational reading, fixed now):
- C-R1: FAIL and |W(g>s) − W(s>g)| ≤ 2; beside it, s pins period_frac ≤ 0.5 in ≥ 7 of 10 policies.
- C-R2: PASS with 6–8 wins and ≤ 2 losses; beside it, m9 pins ≤ 0.5 in 6–9 of 10, and m9 ties g (±2).
- C-R3: PASS with 7–9 wins; beside it, c ties g (±2).
- C-P1: W(a>S) ∈ {2, 3} (hence FAIL); which designs a wins is reported against the lens's "zipdiv and wbqspiflash".
- C-P2: PASS (S wins on ≥ 4); "narrowly" is reported as the count, not scored.
- Headline (task): c ties g, m9 ties g, and W(a>S) ∈ {2, 3}.

## What each outcome means (the lens's §4, with this run's limits)
- C-P1 passes (reports buy the proposer ≥ 4 of 7): the reading is the mechanism; the report summary Avi designed is what
  the model uses. C-P1 fails: "its edge is a habit, not a reading, and the habit is one line in my judge", as A33b/A36
  already suggested; said first, in the plan, by Avi.
- C-R1 passes (g beats s): the reports matter to the rule-writer. Fails (the prediction): a scores-only Opus writes as good
  a rule, taught by the prompt's re-run framing.
- C-R2 passes: a 9B open model on a free CPU runner writes rules that beat TPE under the same rebuild judge, a cell anyone
  can re-run. Fails: the capability floor lies above this configuration (9B, Q4, greedy, thinking off); the judge's catch
  rate on its winners is still a result. This run cannot say whether 120B would pass (m120 is not run).
- C-R3 passes and c ties g: the LLM found what a four-line script finds; the judge that makes every cell countable is Avi's.
- Every outcome is worth saying: the model becomes a subject of the experiment, not its author.

## Reported beside, no criterion
All pairwise counts among b, f, g, s, m9, c (rule races) and a, b, f, S (proposer races) by the same rule; S against the
start set's fixed point; each arm's policies or settings, and how many pin period_frac ≤ 0.5; unreadable replies and
re-asks per reader; first-rebuild failures per reader (the first closure run of the arm's best failed); m9 receipts
(download time, tokens/s for prompt and reply, wall time, CPU model) and the seed-1/seed-2 replay check; S's rationales.

## Decision times and handling
- Each set of tests (rule, proposer) is computed when every new arm's chain in it has ended (each fixed point checked, a
  lower bound, or none), and in any case at **Sat Nov 7 12:00 UTC** on what has landed then (runs still in flight count as
  not checked; `c_score.DEADLINE`).
- Run order (one active farm run of this workstream at a time, max_parallel = the coordinator's share): the m9 batch
  (10 runner jobs) and the round-1 Opus calls first; then `tune_c.py --step` every few minutes sends all due runs as one
  farm run; proposer rounds 2–4 are asked as their previous round lands. If the coordinator allows two active runs, the
  rule and proposer races run as two lanes (`--lane rule`, `--lane prop`), each with at most one active run, so the
  38–87-minute PPU runs do not hold up the short rule-race rounds. Scheduling changes no rule, budget or test.
- Nothing in the arms, prompts, transforms, budgets, judge, tests or predictions changes after this file is hashed. A
  smoke test that forces a plumbing change (m9 workflow or driver) is recorded as an amendment before launch, and the
  amendment says so; no prediction changes. Every deviation is logged in C_RESULT.md with its reason.
- Smoke runs (tag or batch prefix `smoke`) test plumbing only and are excluded from every analysis.

## Caveats known in advance
1. 10 rule races are 5 start sets × 2 seeds, not 10 independent designs; 7 proposer designs. The ±2 tie band is coarse,
   and the 2% margin sits near the 2.3% chaos floor for target nudges (E4).
2. One sampled reply per Opus call (as g and a had): s vs g also differs by sampling; g's two seeds already differ.
3. m9 is greedy: both seeds of a design get the same prompt, so its 10 races likely run 5 distinct policies (like c),
   where g and s have 10 sampled ones.
4. m9 runs with thinking off (Qwen advises against greedy decoding with thinking on, and CPU time); an m9 loss cannot
   separate model size from thinking.
5. The reused arms ran Oct 28–30; the new arms run on the same workflow, image digest and PDK. The flow is deterministic
   (QA-week replays bit-identical), so reuse is sound; a smoke replay of one start run from this branch checks it.
6. The prompts keep design names (above); the instances are told to use nothing else, and their tool calls are logged.
7. All four new arms were built by an agent, not by Avi: the transform, the script's tie rule, the model file, the build
   flags, the decoding, the re-ask form and the tag letters are this file's deterministic choices, recorded before launch.
8. In the plumbing test the 0.8B sibling, decoding greedily, fell into a repetition loop inside its rationale and hit the
   token cap. The 9B may do the same; that is why the one re-ask constrains the reply's form (and the rationale to 1,500
   characters, so the JSON closes within the 2,048-token cap). Unreadable first replies are counted and reported.
