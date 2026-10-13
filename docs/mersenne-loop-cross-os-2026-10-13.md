# Actual generic Mersenne loop versioning on three native OSes

[Native run 38349470617](https://github.com/forge-language/forge-benchmarks/actions/runs/38349470617) completed all six jobs. Each job uses 60 balanced triples per workload, matched algorithms, common per-run SDK/clock and independent output references. All 720 direct checks, 5400 prewarms and 5400 measured executions matched.

| Platform / repeat | Workload | Candidate / before (95% interval) | Candidate / Rust (95% interval) |
| --- | --- | ---: | ---: |
| macos-15-0 | lcg | 1.8418 [1.8254,1.8816] | 1.6048 [1.5833,1.6379] |
| macos-15-0 | primes | 0.7382 [0.7268,0.7505] | 0.7005 [0.6886,0.7090] |
| macos-15-0 | scan | 1.0095 [0.9891,1.0212] | 0.9903 [0.9818,1.0023] |
| macos-15-0 | builder | 2.2748 [2.1765,2.3448] | 1.3014 [1.2633,1.3347] |
| macos-15-0 | immutable | 1.0053 [0.9844,1.0095] | 18.1737 [17.3318,18.9020] |
| macos-15-1 | lcg | 1.8360 [1.8306,1.8487] | 1.5986 [1.5880,1.6047] |
| macos-15-1 | primes | 0.7341 [0.7290,0.7382] | 0.7017 [0.6995,0.7065] |
| macos-15-1 | scan | 0.9954 [0.9804,1.0087] | 1.0042 [0.9932,1.0116] |
| macos-15-1 | builder | 2.2670 [2.2265,2.2997] | 1.3049 [1.2822,1.3163] |
| macos-15-1 | immutable | 0.9973 [0.9874,1.0083] | 17.0406 [16.6695,17.6462] |
| ubuntu-24.04-0 | lcg | 1.0002 [0.9994,1.0008] | 1.8552 [1.8544,1.8559] |
| ubuntu-24.04-0 | primes | 0.7953 [0.7939,0.7964] | 1.0042 [1.0027,1.0054] |
| ubuntu-24.04-0 | scan | 1.0383 [1.0368,1.0397] | 0.9430 [0.9415,0.9447] |
| ubuntu-24.04-0 | builder | 1.4221 [1.4206,1.4235] | 1.3383 [1.3373,1.3395] |
| ubuntu-24.04-0 | immutable | 1.0018 [1.0009,1.0035] | 22.5709 [22.5437,22.6670] |
| ubuntu-24.04-1 | lcg | 1.0001 [0.9998,1.0004] | 1.8548 [1.8535,1.8557] |
| ubuntu-24.04-1 | primes | 0.7961 [0.7950,0.7971] | 1.0071 [1.0051,1.0086] |
| ubuntu-24.04-1 | scan | 0.9973 [0.9883,1.0106] | 0.9016 [0.8945,0.9105] |
| ubuntu-24.04-1 | builder | 1.4215 [1.4199,1.4230] | 1.3382 [1.3359,1.3394] |
| ubuntu-24.04-1 | immutable | 0.9992 [0.9975,1.0009] | 22.5266 [22.4533,22.5695] |
| windows-2022-0 | lcg | 1.0000 [0.9992,1.0005] | 1.8586 [1.8566,1.8617] |
| windows-2022-0 | primes | 1.0626 [1.0594,1.0650] | 1.2455 [1.2426,1.2479] |
| windows-2022-0 | scan | 0.9992 [0.9988,1.0003] | 0.5326 [0.5320,0.5331] |
| windows-2022-0 | builder | 1.2939 [1.2921,1.2954] | 0.9577 [0.9565,0.9589] |
| windows-2022-0 | immutable | 1.1184 [1.1165,1.1207] | 55.9050 [55.4969,56.1762] |
| windows-2022-1 | lcg | 1.0000 [0.9995,1.0005] | 1.8569 [1.8559,1.8579] |
| windows-2022-1 | primes | 1.0626 [1.0602,1.0653] | 1.2430 [1.2395,1.2451] |
| windows-2022-1 | scan | 0.9998 [0.9980,1.0006] | 0.5332 [0.5324,0.5340] |
| windows-2022-1 | builder | 1.2942 [1.2925,1.2965] | 0.9596 [0.9581,0.9621] |
| windows-2022-1 | immutable | 1.1195 [1.1168,1.1221] | 55.5374 [55.3099,55.7589] |

This run measures unmodified compiler 5481e3a, with no generated-C changes. macOS LCG improves about 1.84× old Forge and reaches about 1.60× Rust; Linux/Windows LCG remain near old Forge. It confirms the generic implementation reproduces the screened Apple M1 gain. Prime/scan gaps remain; this does not complete the entire target.
