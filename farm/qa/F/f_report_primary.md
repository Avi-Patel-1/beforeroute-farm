| config | design / platform | T0 | published claim | replay claim (gap) | first rebuild at | its slack | its claim | d1 | first rebuild judge | chain (clock: pass/fail) | kept |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ee001 | aes / asap7 | 385.5 | 291.5 | 291.5 (-0.00%) | 295 | 7.4 | 287.6 | -1.3% | pass | 295: pass | 295 |
| ee008 | jpeg / asap7 | 400 | 530.7 | 530.7 (+0.00%) | 535 | -2.1 | 537.1 | +1.2% | FAIL (setup, hold) | 535: fail | – |
| ee011 | ibex / asap7 | 1000 | 953.7 | 953.7 (+0.00%) | 955 | 29.6 | 925.4 | -3.0% | pass | 955: pass | 955 |
| ee013 | aes / asap7 | 368.2 | 354.2 | 354.2 (+0.00%) | 355 | 12.8 | 342.2 | -3.4% | pass | 355: pass | 355 |
| ee016 | jpeg / asap7 | 560.5 | 508.9 | 508.9 (+0.00%) | 510 | -1.3 | 511.3 | +0.5% | FAIL (setup) | 510: fail | 560.5 |
| ee037 | sboxpipe / asap7 | 312 | 176.5 | 176.5 (+0.00%) | 180 | 9.7 | 170.3 | -3.5% | pass | 180: pass | 180 |
| ee054 | aes / asap7 | 340 | 309.9 | 309.9 (-0.00%) | 310 | 15.7 | 294.3 | -5.0% | pass | 310: pass | 310 |
| ee074 | mult16 / asap7 | 653 | 401.5 | 401.5 (+0.00%) | 405 | -0.6 | 405.6 | +1.0% | FAIL (setup) | 405: fail | 653 |
| ee075 | adder64 / asap7 | 360 | 222.7 | 222.7 (+0.00%) | 225 | 7.8 | 217.2 | -2.5% | pass | 225: pass | 225 |
| ee087 | mult16 / asap7 | 615 | 462.7 | 462.7 (-0.00%) | 465 | 20.7 | 444.3 | -4.0% | pass | 465: pass | 465 |
| ee097 | aes / asap7 | 340 | 327.7 | 327.7 (+0.00%) | 330 | 7.7 | 322.3 | -1.7% | pass | 330: pass | 330 |
| oa-aes-a7 | aes / asap7 | 140.237 | 427.7 | 427.7 (+0.00%) | 430 | -23.6 | 453.6 | +6.1% | FAIL (setup) | 430: fail | – |
| oa-ibex-a7 | ibex / asap7 | 604.088 | 1254.2 | 1254.2 (+0.00%) | 1255 | -97.1 | 1352.1 | +7.8% | FAIL (setup) | 1255: fail | – |
| oa-aes-s130 | aes / sky130hd | 3.3 | 3.801 | 3.801 (+0.00%) | 3.85 | -0.171 | 4.021 | +5.8% | FAIL (setup) | 3.85: fail | – |

verdict: PREDICTION FAILS (P1 median optimism < 3%)
n_registered: 14
n_replay_landed: 14
n_reproduced: 14
n_first_rebuild_landed: 14
median_d1: -0.014988078484199696
first_rebuild_fails: ['ee008', 'ee016', 'ee074', 'oa-aes-a7', 'oa-ibex-a7', 'oa-aes-s130']
first_rebuild_failures_by_part: {'ee008': ['setup', 'hold'], 'ee016': ['setup'], 'ee074': ['setup'], 'oa-aes-a7': ['setup'], 'oa-ibex-a7': ['setup'], 'oa-aes-s130': ['setup']}
P2_setup_only: True
by_source: {'EDA-env': {'n': 11, 'n_with_d1': 11, 'median_d1': -0.02478078685894025, 'fails': 3}, 'ORFS-agent': {'n': 3, 'n_with_d1': 3, 'median_d1': 0.060757184979762124, 'fails': 3}}
by_replay_slack_sign: {'negative (claim from a failing run)': {'n': 4, 'n_with_d1': 4, 'median_d1': 0.05927769436662722, 'fails': 4}, 'non-negative (claim from a passing run)': {'n': 10, 'n_with_d1': 10, 'median_d1': -0.027196394967662185, 'fails': 2}}
d1_vs_published_median: -0.01498821020690605
kept_over_C0_median: 1.008583709808164
not_reproduced: []
