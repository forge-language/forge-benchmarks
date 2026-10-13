# Integrated compiler `420d66f`: native Linux/macOS/Windows verification

**Similar positive scan/builder effects are established on all three tested OSes. The full cross-OS Rust 1.10 target is not achieved.** This measures the shipped compiler unchanged, with no generated-C patch. [Run 38352449216](https://github.com/forge-language/forge-benchmarks/actions/runs/38352449216) completed all six independent native jobs. Every job passed 120 direct oracle checks, 900 same-input prewarms and 900 measured executions ; 720/5400/5400 across the matrix. Native Windows temporary-file and filesystem checks passed before measurement.

Before compiler `9f70e9d` and after `420d66f` use the same per-run SDK archives/installed headers, matched Forge/Rust algorithms, dimensions, clock and inputs. All six three-way orders are balanced at 60 triples per workload. C uses O3/native tuning/full LTO, Rust uses opt-level3/native/thin LTO. Paired bootstrap intervals are row-wise 95%, not a universal-language or simultaneous-all-row proof. Compare within runner; different CPUs/toolchains confound OS-only causality.

| Platform / repeat | CPU | Workload | After / old Forge (95% interval) | After / Rust (95% interval) |
| --- | --- | --- | ---: | ---: |
| macos-15-0 | Apple M1 (Virtual) | lcg | 1.8365 [1.8270,1.8506] | 1.6022 [1.5966,1.6084] |
| macos-15-0 | Apple M1 (Virtual) | primes | 1.0033 [0.9988,1.0104] | 0.9569 [0.9531,0.9640] |
| macos-15-0 | Apple M1 (Virtual) | scan | 8.9665 [8.8940,9.0084] | 8.9521 [8.9117,8.9865] |
| macos-15-0 | Apple M1 (Virtual) | builder | 5.7624 [5.7407,5.7822] | 3.3031 [3.2847,3.3153] |
| macos-15-0 | Apple M1 (Virtual) | immutable | 1.3439 [1.3381,1.3526] | 22.3525 [22.1838,22.4811] |
| macos-15-1 | Apple M1 (Virtual) | lcg | 1.9026 [1.8611,1.9719] | 1.6381 [1.5876,1.7276] |
| macos-15-1 | Apple M1 (Virtual) | primes | 1.0017 [0.9586,1.0207] | 0.9359 [0.8901,0.9660] |
| macos-15-1 | Apple M1 (Virtual) | scan | 8.6435 [8.0123,8.9783] | 8.4066 [7.8233,9.4815] |
| macos-15-1 | Apple M1 (Virtual) | builder | 5.2992 [5.0331,5.7504] | 3.2889 [2.9824,3.4964] |
| macos-15-1 | Apple M1 (Virtual) | immutable | 1.3897 [1.3220,1.4656] | 27.1283 [25.7875,28.4705] |
| ubuntu-24.04-0 | see raw hardware record | lcg | 0.9997 [0.9993,1.0003] | 1.8551 [1.8538,1.8559] |
| ubuntu-24.04-0 | see raw hardware record | primes | 0.7980 [0.7968,0.7994] | 1.0160 [1.0149,1.0179] |
| ubuntu-24.04-0 | see raw hardware record | scan | 2.6112 [2.5952,2.6314] | 2.4331 [2.4166,2.4533] |
| ubuntu-24.04-0 | see raw hardware record | builder | 1.5803 [1.5771,1.5835] | 1.7225 [1.7209,1.7246] |
| ubuntu-24.04-0 | see raw hardware record | immutable | 1.1647 [1.1617,1.1669] | 21.9766 [21.9077,22.0418] |
| ubuntu-24.04-1 | Xeon Platinum 8573C | lcg | 1.0069 [0.9951,1.0258] | 1.6855 [1.6636,1.7037] |
| ubuntu-24.04-1 | Xeon Platinum 8573C | primes | 1.1955 [1.1830,1.2069] | 1.4069 [1.3918,1.4241] |
| ubuntu-24.04-1 | Xeon Platinum 8573C | scan | 2.1163 [2.0973,2.1615] | 2.3824 [2.3541,2.4198] |
| ubuntu-24.04-1 | Xeon Platinum 8573C | builder | 1.6620 [1.6271,1.6895] | 1.4427 [1.4221,1.4868] |
| ubuntu-24.04-1 | Xeon Platinum 8573C | immutable | 1.1076 [1.0871,1.1273] | 22.1383 [21.7101,22.3306] |
| windows-2022-0 | AMD EPYC 7763 | lcg | 0.9996 [0.9989,1.0002] | 1.8563 [1.8550,1.8578] |
| windows-2022-0 | AMD EPYC 7763 | primes | 1.0646 [1.0621,1.0663] | 1.2496 [1.2464,1.2513] |
| windows-2022-0 | AMD EPYC 7763 | scan | 4.4170 [4.4129,4.4195] | 2.3560 [2.3505,2.3599] |
| windows-2022-0 | AMD EPYC 7763 | builder | 2.0815 [2.0769,2.0882] | 1.5452 [1.5407,1.5482] |
| windows-2022-0 | AMD EPYC 7763 | immutable | 1.5666 [1.5626,1.5695] | 78.3348 [77.8535,78.5376] |
| windows-2022-1 | see raw hardware record | lcg | 0.9998 [0.9993,1.0001] | 1.8573 [1.8565,1.8578] |
| windows-2022-1 | see raw hardware record | primes | 1.0342 [1.0274,1.0373] | 1.2213 [1.2181,1.2263] |
| windows-2022-1 | see raw hardware record | scan | 7.4079 [6.7166,8.1139] | 4.4128 [3.9154,4.7114] |
| windows-2022-1 | see raw hardware record | builder | 1.9825 [1.9803,2.0160] | 1.7150 [1.7052,1.7404] |
| windows-2022-1 | see raw hardware record | immutable | 1.4030 [1.3968,1.4179] | 66.2269 [65.8337,66.3640] |

Scan gains over old Forge are Linux 2.12–2.61×, macOS 8.64–8.97× and Windows 4.42–7.41×. Builder gains are Linux 1.58–1.66×, macOS 5.30–5.76× and Windows 1.98–2.08×. All six per-workload lower interval bounds exceed 1.10 for scan and builder. macOS LCG gains 1.84–1.90× old Forge and reaches 1.60–1.64× Rust; Linux/Windows LCG stay near old Forge.

ARM64 checked hardware remainder restores prime throughput to about original Forge, resolving the repeated 0.73× regression from reciprocal caching. However macOS prime remains 0.936–0.957× Rust, and one Linux EPYC job prime remains 1.016× Rust and 0.798× old Forge. Those are unresolved target misses/regressions; they are not discarded. The other Linux prime and both Windows prime rows exceed Rust 1.10. Immutable append still has different allocation/lifetime policies and cannot establish language-wide throughput.

The local AMD BC-250 60-group full suite passes all five Rust 1.10 row-wise thresholds, but that success must not be generalized to every OS. [Local full suite](periodic-compiler-full-60-2026-10-13.md). The actual compiler incorporates generic guarded reserved buffers, Mersenne recurrence loop versioning, periodic byte sums and the ARM64 remainder policy; public APIs and JavaScript behavior are retained. [Proof and exact validation limits](periodic-sum-lowering-2026-10-13.md), [run/failure ledger](cross-os-attempts-2026-10-13.json).

HTTP capacity/throughput was separately observed on the Linux developer machine: repeated 128000 request lanes and 2692 req/s median, with high variance and no absolute server/user maximum. Those results are not cross-OS HTTP evidence. [HTTP conditions and complete attempts](http-v32-capacity-128k-paired-2026-10-12.md).

Frozen sources, SDKs, binaries, assembly and metadata are in `cross-os-integrated-compiler-2026-10-13.raw.tar.gz`; SHA-256 is recorded in `cross-os-archives-2026-10-13.sha256`. All earlier failures, regressions and rejected prototypes remain preserved.
