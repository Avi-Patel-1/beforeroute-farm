# Workstream L — result: the finished loop, hands-off, on fresh blocks

Pre-registration: docs/qa_week/L_PREREG.md with Amendment L.1 (hash lines of 2026-11-10 in farm/prereg_hashes.txt,
branch qa-l-loop), written before any run. Runs: 42742364760 (smoke, then blocks x and u; commit bf9c244) and
42747705365 (block s after Amendment L.1). Scored 2026-11-10 with the committed farm/qa/L/score.py. No model was called
and nobody acted between the push and the uploaded results. Nothing was re-run after a result was seen.

**Bottom line.** P1 failed: the loop matched or beat plain Bayesian search in 2 of 6 races (needed 4). It matched or
beat on both USB races with half the flows, lost both races on the repaired XTEA by 8 and 14%, and the two SHA-3 races
did not complete. P2 held on every build the loop kept: 4 of 4 are signoff-clean. The loop itself ran end to end
without a person, which is what slide 6 listed as future work.

## Verdicts
| | Registered | Outcome | Held? |
|---|---|---|---|
| P1 | The loop matches or beats plain Bayesian search (kept clock no more than 2% slower) in at least 4 of 6 races, with 2 search runs against 8 | 2 of 6: one beat, one match, two losses, two races missing | **no** |
| P2 | Every kept build of the loop is signoff-clean (judge passed again; Magic DRC, KLayout DRC, LVS and antenna all 0) | 4 of 4 kept builds clean (XOR 0 as well) | **yes**, on the four builds that exist |

## Every race (clocks in ns; a flow is one place-and-route run after the shared 9 prep runs)
| block | seed | Bayesian kept | loop kept | loop against Bayesian | verdict | Bayesian flows / hours | loop flows / hours | loop signoff |
|---|---|---|---|---|---|---|---|---|
| usb | 1 | 4.90 | 4.70 | 4.3% faster | beat | 12 / 0.45 | 6 / 0.20 | clean at 4.70 |
| usb | 2 | 4.80 | 4.80 | equal | match | 12 / 0.41 | 6 / 0.26 | clean at 4.80 |
| xtea_live | 1 | 9.75 | 11.35 | 14.1% slower | loss | 12 / 1.40 | 4 / 0.26 | clean at 11.35 |
| xtea_live | 2 | 10.70 | 11.60 | 7.8% slower | loss | 12 / 0.57 | 4 / 0.38 | clean at 11.60 |
| sha3 | 1, 2 | none | none | | missing | | | |

## Why the loop lost on the repaired XTEA
The four-line rule pins the clock at the floor of the search space (0.45 of the default period: 11.71 ns here) and
copies the best start run's synthesis strategy (AREA 3). On the live cipher that was not a push: both pinned runs met
timing at 11.71 ns with about 0.4 ns to spare, the first rebuild at 11.30 ns failed, and the chain stopped one step
back at 11.35 or 11.60 ns. Bayesian search's eight runs found settings whose chains reached 9.75 and 10.70 ns. So on
this block the other knobs mattered more than the clock target, the opposite of the five race designs of workstream C.
The rule's reach is limited by where the floor sits relative to what the block can meet, and by the strategy it copies.

## The repaired XTEA's rebuild chain (the live counterpart of slide 4)
Bayesian winner, seed 1: built at 14.98 ns, claimed 11.26 ns. Rebuilds at 11.30, 10.50, 9.90 and 9.75 ns all passed:
88.5 to 102.6 MHz on one setting, 1.16x, still passing at the four-rebuild cap. Seed 2: 12.17 ns claimed 11.23;
rebuilds at 11.25, 11.05, 10.85 and 10.70 ns all passed (88.9 to 93.5 MHz). With live logic the staircase is there,
and it is smaller than the 1.38x of the control-loop version on the slide.

## SHA-3
Under the stock flow the shipped RTL fails LibreLane's synthesis lint (Amendment L.1). With the lint switched to a
warning it builds, but each run takes 30 to 57 minutes on a GitHub runner; the prep job reached its 350-minute limit
after the reference run and 3 of the 8 start runs. The arm jobs then started on that partial start set, which is not
the registered protocol, and were cancelled. Both races count as not matched, as registered. The harness's
one-job-per-stage layout is too slow for a block of this size; that is a limit of this implementation.

## Caveats
1. Two blocks completed, both under 2,000 cells, two seeds each. Four races are a small sample.
2. On usb the loop's edge is within one seed's spread: a beat by 4.3% and an exact tie.
3. The baseline is plain TPE with 8 search runs after 8 start runs, the project's standard budget.
4. The chain rule is workstream B's (one step back after a failed first rebuild). A longer step-back budget might have
   changed the XTEA chains; it was not run.

## Say it as
> "I ran the finished loop hands-off on blocks it had never seen, with the prediction written down first, and the
> prediction failed. On the USB core the four-line rule matched Bayesian search with half the runs. On the repaired
> XTEA it lost by 8 to 14 percent, because there the clock floor was not a real push and the other settings mattered.
> So the simple baseline is strong but not universal, and every build the loop kept passed full signoff."

Do not say: "the loop beats Bayesian search" (2 of 4 completed races, 2 of 6 registered); "validated on SHA-3" (not
completed); "the rule needs no search" (on the repaired XTEA search won).
