# Bounded word-size modular power: rejected ARM64 result

[Native run 38348975326](https://github.com/forge-language/forge-benchmarks/actions/runs/38348975326) completed all six jobs. Each job uses 60 balanced triples per workload, matched algorithms, common per-run SDK/clock and independent output references. All 720 direct checks, 5400 prewarms and 5400 measured executions matched.

| Platform / repeat | Workload | Candidate / before (95% interval) | Candidate / Rust (95% interval) |
| --- | --- | ---: | ---: |
| macos-15-0 | lcg | 1.8760 [1.8423,1.9359] | 1.6205 [1.5778,1.6680] |
| macos-15-0 | primes | 1.1848 [1.1654,1.1950] | 0.8253 [0.8190,0.8344] |
| macos-15-0 | scan | 9.0238 [8.9137,9.3866] | 9.0141 [8.8441,9.2549] |
| macos-15-0 | builder | 2.5567 [2.4677,2.6698] | 3.4194 [3.3146,3.5541] |
| macos-15-0 | immutable | 1.3394 [1.3246,1.3623] | 22.6361 [22.2960,23.5444] |
| macos-15-1 | lcg | 1.8333 [1.7952,1.8670] | 1.5947 [1.5795,1.6250] |
| macos-15-1 | primes | 1.1849 [1.1733,1.2019] | 0.8329 [0.8241,0.8443] |
| macos-15-1 | scan | 9.0022 [8.9089,9.2099] | 9.0279 [8.9581,9.1318] |
| macos-15-1 | builder | 2.5178 [2.4875,2.5478] | 3.2980 [3.2399,3.3329] |
| macos-15-1 | immutable | 1.3366 [1.2932,1.3544] | 23.4161 [22.7369,24.1749] |
| ubuntu-24.04-0 | lcg | 1.0022 [1.0011,1.0029] | 1.6757 [1.6737,1.6769] |
| ubuntu-24.04-0 | primes | 1.1801 [1.1786,1.1844] | 1.6663 [1.6617,1.6738] |
| ubuntu-24.04-0 | scan | 2.1110 [2.1080,2.1182] | 2.3841 [2.3687,2.3952] |
| ubuntu-24.04-0 | builder | 1.4045 [1.4009,1.4085] | 1.4361 [1.4330,1.4426] |
| ubuntu-24.04-0 | immutable | 1.1267 [1.1155,1.1343] | 22.0336 [21.8766,22.1016] |
| ubuntu-24.04-1 | lcg | 0.9999 [0.9996,1.0004] | 1.8555 [1.8550,1.8558] |
| ubuntu-24.04-1 | primes | 1.2566 [1.2546,1.2577] | 1.2679 [1.2646,1.2694] |
| ubuntu-24.04-1 | scan | 3.5928 [3.5873,3.6001] | 3.3402 [3.3358,3.3433] |
| ubuntu-24.04-1 | builder | 1.3805 [1.3799,1.3814] | 1.8238 [1.8226,1.8251] |
| ubuntu-24.04-1 | immutable | 1.1988 [1.1962,1.2008] | 22.5289 [22.4758,22.5944] |
| windows-2022-0 | lcg | 0.9999 [0.9995,1.0002] | 1.8569 [1.8558,1.8575] |
| windows-2022-0 | primes | 1.0297 [1.0263,1.0332] | 1.2734 [1.2715,1.2750] |
| windows-2022-0 | scan | 8.0215 [6.7048,8.0854] | 4.6586 [3.9200,4.6932] |
| windows-2022-0 | builder | 1.9248 [1.9199,1.9596] | 1.7094 [1.7064,1.7363] |
| windows-2022-0 | immutable | 1.4178 [1.4032,1.4214] | 66.5707 [66.2248,66.8055] |
| windows-2022-1 | lcg | 1.0006 [0.9997,1.0021] | 1.8573 [1.8552,1.8589] |
| windows-2022-1 | primes | 1.0249 [1.0228,1.0284] | 1.2765 [1.2753,1.2800] |
| windows-2022-1 | scan | 4.4150 [4.4108,4.4213] | 2.3529 [2.3486,2.3554] |
| windows-2022-1 | builder | 1.5538 [1.5447,1.5613] | 1.4904 [1.4835,1.4981] |
| windows-2022-1 | immutable | 1.5520 [1.5457,1.5566] | 79.4604 [78.8937,79.7405] |

The candidate is not adopted. macOS prime reaches only 0.825–0.833× Rust, worse than the earlier hybrid candidate, while x86 results remain positive. This is evidence that fewer-bit arithmetic and added fast-path branches do not necessarily improve a target. All negative observations remain preserved.
