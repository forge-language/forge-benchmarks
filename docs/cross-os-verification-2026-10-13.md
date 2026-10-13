# Cross-OS verification: measured regressions and remaining work

Status: **not achieved**. Linux developer-machine gains are not evidence of the same effect on another OS. Sixteen hosted-runner attempts preserve74 completed CPU reports, four failed-before-measurement reports and all88 job outcomes (74 successes,14 failures). Native Windows measurement now completed twice, but scan and builder remain below Rust and the macOS prime regression persists.

## Protocol

The pinned before/after compiler versions share identical SDK archives, installed headers, matched Forge/Rust small-prime algorithms and the common clock on each runner. Both executables run the same runtime dimensions/seeds, with six balanced three-way orders and checked per-input warmup. Each job uses 60 groups per workload. Processes are unpinned on every OS. Native C uses -O3/native tuning/-flto; Rust uses opt-level=3/target-cpu=native/thin LTO. Compare ratios within a runner; independent hosted machines can differ, and absolute times do not isolate OS effects.

## Prime workload evidence

| Run | Platform / repeat | Experiment | Candidate / old Forge (95% interval) | Candidate / Rust (95% interval) |
| --- | --- | --- | ---: | ---: |
| [38326482053](https://github.com/forge-language/forge-benchmarks/actions/runs/38326482053) | macos-15-0 | none | 0.7345 [0.7297, 0.7383] | 0.7007 [0.6968, 0.7038] |
| [38326482053](https://github.com/forge-language/forge-benchmarks/actions/runs/38326482053) | macos-15-1 | none | 0.7353 [0.7305, 0.7439] | 0.7008 [0.6978, 0.7043] |
| [38326482053](https://github.com/forge-language/forge-benchmarks/actions/runs/38326482053) | ubuntu-24.04-0 | none | 0.7995 [0.7989, 0.8006] | 1.0109 [1.0083, 1.0126] |
| [38326482053](https://github.com/forge-language/forge-benchmarks/actions/runs/38326482053) | ubuntu-24.04-1 | none | 0.7921 [0.7913, 0.7930] | 1.0152 [1.0145, 1.0168] |
| [38328233196](https://github.com/forge-language/forge-benchmarks/actions/runs/38328233196) | macos-15-0 | none | 0.7310 [0.7274, 0.7380] | 0.7020 [0.6944, 0.7047] |
| [38328233196](https://github.com/forge-language/forge-benchmarks/actions/runs/38328233196) | macos-15-1 | none | 0.7361 [0.7334, 0.7406] | 0.7015 [0.6973, 0.7042] |
| [38328233196](https://github.com/forge-language/forge-benchmarks/actions/runs/38328233196) | ubuntu-24.04-0 | none | 1.1413 [1.1405, 1.1427] | 1.3242 [1.3219, 1.3255] |
| [38328233196](https://github.com/forge-language/forge-benchmarks/actions/runs/38328233196) | ubuntu-24.04-1 | none | 0.9337 [0.9317, 0.9349] | 1.1324 [1.1286, 1.1372] |
| [38328235802](https://github.com/forge-language/forge-benchmarks/actions/runs/38328235802) | macos-15-0 | bounded-hint | 0.7138 [0.7063, 0.7212] | 0.6863 [0.6798, 0.7001] |
| [38328235802](https://github.com/forge-language/forge-benchmarks/actions/runs/38328235802) | macos-15-1 | bounded-hint | 0.7177 [0.6986, 0.7526] | 0.6807 [0.6616, 0.7073] |
| [38328235802](https://github.com/forge-language/forge-benchmarks/actions/runs/38328235802) | ubuntu-24.04-0 | bounded-hint | 0.9840 [0.9831, 0.9856] | 1.2436 [1.2405, 1.2450] |
| [38328235802](https://github.com/forge-language/forge-benchmarks/actions/runs/38328235802) | ubuntu-24.04-1 | bounded-hint | 1.3560 [1.3545, 1.3574] | 1.5884 [1.5850, 1.5893] |
| [38329828386](https://github.com/forge-language/forge-benchmarks/actions/runs/38329828386) | macos-15-0 | none | 0.7259 [0.7154, 0.7323] | 0.6913 [0.6818, 0.7115] |
| [38329828386](https://github.com/forge-language/forge-benchmarks/actions/runs/38329828386) | macos-15-1 | none | 0.7310 [0.7219, 0.7351] | 0.7016 [0.6957, 0.7052] |
| [38329828386](https://github.com/forge-language/forge-benchmarks/actions/runs/38329828386) | ubuntu-24.04-0 | none | 0.7912 [0.7901, 0.7924] | 1.0086 [1.0073, 1.0105] |
| [38329828386](https://github.com/forge-language/forge-benchmarks/actions/runs/38329828386) | ubuntu-24.04-1 | none | 0.8010 [0.7973, 0.8039] | 1.0082 [1.0034, 1.0141] |
| [38329830957](https://github.com/forge-language/forge-benchmarks/actions/runs/38329830957) | macos-15-0 | bounded-inline | 0.7307 [0.7265, 0.7468] | 0.7065 [0.6859, 0.7195] |
| [38329830957](https://github.com/forge-language/forge-benchmarks/actions/runs/38329830957) | macos-15-1 | bounded-inline | 0.7356 [0.7291, 0.7424] | 0.7053 [0.7015, 0.7081] |
| [38329830957](https://github.com/forge-language/forge-benchmarks/actions/runs/38329830957) | ubuntu-24.04-0 | bounded-inline | 1.1077 [1.1055, 1.1082] | 1.4094 [1.4073, 1.4106] |
| [38329830957](https://github.com/forge-language/forge-benchmarks/actions/runs/38329830957) | ubuntu-24.04-1 | bounded-inline | 1.5268 [1.5106, 1.5319] | 1.7698 [1.7647, 1.7779] |

The unchanged shipped reciprocal lowering repeatedly regresses the ARM64 Apple Clang 17 prime workload to about 0.73–0.74 of baseline Forge throughput and about 0.70 of Rust throughput. This contradicts the requested cross-OS similarity. Hosted x86 Linux runs also show both gains and regressions across independent machines, so stability is not established there. The initial reports lack detailed CPU model identification; later runs capture hardware identity and disassembly to investigate this variation.

The `bounded-hint` experiment skips correction only under n < 2^43 and d <= 2^21 and exposes the proven remainder range to the optimizer. A later `bounded-inline` experiment also forces the two pure, nonrecursive benchmark prime helpers to inline. Both preserve exact outputs and are explicitly generated-C prototypes, not changes in the shipped compiler. Neither resolves the ARM64 regression, so neither is adopted as a cross-OS improvement. The arithmetic probe checks 301,194 oracle inputs in each of five UBSan configurations, plus exceptional operands; this establishes its stated arithmetic correctness, not speed.

## Windows failures and fixes

The first Windows attempts fail to compile an invalid `MOVEFILE_FAIL_IF_EXISTS` flag. Runtime `dcbb192` removes it, preserves no-replace semantics, validates temp-path bounds and bounds collision retries. A native Windows test checks collisions with real files, cleanup after access errors and retry exhaustion. The next failures expose const-incompatible `_spawnvp` arguments; Forge `7ac669a` supplies a read-only pointer vector with original ownership and error semantics. The historical before compiler gets only a diagnostic downgrade for that known cold-path issue; native workload compilation retains its explicit flags.

Subsequent Windows attempts fail on an undeclared POSIX `close` in HTTP cleanup and report a stat-structure mismatch. Stdlib `6aa2866` uses the Windows CRT file close and matching 64-bit stat API/structure. Filesystem checks now verify size and file/directory classification. Linux runtime four tests, stdlib eleven tests, and Forge twenty-two suites pass; these Linux checks do not replace the native Windows tests.

The updated SDK is pinned in Forge `12d8ff4`. [Run 38330922225](https://github.com/forge-language/forge-benchmarks/actions/runs/38330922225) completed four Linux/macOS reports. Both native Windows temporary-file and filesystem tests passed, but a CRLF-only checkout difference falsely failed source-integrity validation before performance measurement. The verifier now checks canonical Git content and still rejects real edits; a Git fixture exercises both cases. [Run 38331767668](https://github.com/forge-language/forge-benchmarks/actions/runs/38331767668) then passed that gate and compiled both Forge programs, but Rust failed to link the shared QPC clock because the object followed its import library. The harness now adds `-lkernel32` after that object.

[Run 38337628850](https://github.com/forge-language/forge-benchmarks/actions/runs/38337628850) completed both independent native Windows jobs. Each report contains 120 direct oracle checks, 900 same-input prewarms and 900 measured executions. Both Windows API tests passed before measurement. This is evidence for Windows execution and the rows below; it does not establish a universal speedup.

## Prior unchanged compiler `12d8ff4` results

Ratios are throughput ratios (reference elapsed time / candidate elapsed time); greater than one is faster. Each cell shows median [row-wise paired-bootstrap 95% interval]. Linux/macOS rows use run 38330922225; Windows rows use 38337628850. All use shipped compiler `12d8ff4` without generated-C changes and the same final runtime/stdlib pins.

| Platform / repeat | CPU | Workload | Candidate / old Forge | Candidate / Rust |
| --- | --- | --- | ---: | ---: |
| macos-15-0 | Apple M1 (Virtual) | lcg | 1.0149 [0.9844, 1.0395] | 0.8672 [0.8502, 0.9000] |
| macos-15-0 | Apple M1 (Virtual) | primes | 0.7605 [0.7295, 0.7794] | 0.7107 [0.6929, 0.7351] |
| macos-15-0 | Apple M1 (Virtual) | scan | 0.9984 [0.9881, 1.0413] | 0.9935 [0.9622, 1.0276] |
| macos-15-0 | Apple M1 (Virtual) | builder | 0.9846 [0.9559, 1.0113] | 0.5633 [0.5499, 0.6095] |
| macos-15-0 | Apple M1 (Virtual) | immutable | 1.0020 [0.9841, 1.0332] | 17.8170 [17.5046, 18.9820] |
| macos-15-1 | Apple M1 (Virtual) | lcg | 0.9988 [0.9976, 0.9999] | 0.8731 [0.8700, 0.8744] |
| macos-15-1 | Apple M1 (Virtual) | primes | 0.7330 [0.7272, 0.7376] | 0.7001 [0.6944, 0.7046] |
| macos-15-1 | Apple M1 (Virtual) | scan | 0.9962 [0.9665, 1.0227] | 0.9910 [0.9786, 1.0178] |
| macos-15-1 | Apple M1 (Virtual) | builder | 1.0050 [0.9871, 1.0225] | 0.5675 [0.5625, 0.5805] |
| macos-15-1 | Apple M1 (Virtual) | immutable | 0.9993 [0.9864, 1.0064] | 17.4170 [16.9957, 18.2875] |
| ubuntu-24.04-0 | AMD EPYC 7763 | lcg | 1.0003 [0.9998, 1.0006] | 1.8552 [1.8546, 1.8554] |
| ubuntu-24.04-0 | AMD EPYC 7763 | primes | 0.7997 [0.7986, 0.8010] | 1.0101 [1.0083, 1.0116] |
| ubuntu-24.04-0 | AMD EPYC 7763 | scan | 1.0135 [1.0120, 1.0145] | 0.9211 [0.9192, 0.9224] |
| ubuntu-24.04-0 | AMD EPYC 7763 | builder | 1.0795 [1.0768, 1.0815] | 1.0148 [1.0124, 1.0168] |
| ubuntu-24.04-0 | AMD EPYC 7763 | immutable | 0.9997 [0.9963, 1.0034] | 22.4855 [22.4228, 22.5428] |
| ubuntu-24.04-1 | Intel Xeon Platinum 8573C | lcg | 0.9992 [0.9966, 1.0015] | 1.6726 [1.6682, 1.6741] |
| ubuntu-24.04-1 | Intel Xeon Platinum 8573C | primes | 1.2116 [1.2086, 1.2163] | 1.4078 [1.4030, 1.4098] |
| ubuntu-24.04-1 | Intel Xeon Platinum 8573C | scan | 0.9959 [0.9925, 0.9999] | 1.1394 [1.1327, 1.1429] |
| ubuntu-24.04-1 | Intel Xeon Platinum 8573C | builder | 0.7941 [0.7907, 0.7997] | 0.6885 [0.6859, 0.6914] |
| ubuntu-24.04-1 | Intel Xeon Platinum 8573C | immutable | 1.0046 [0.9910, 1.0155] | 19.9228 [19.7157, 20.0396] |
| windows-2022-0 | AMD EPYC 7763 | lcg | 1.0002 [0.9994, 1.0006] | 1.8585 [1.8565, 1.8592] |
| windows-2022-0 | AMD EPYC 7763 | primes | 1.0574 [1.0539, 1.0593] | 1.2404 [1.2387, 1.2413] |
| windows-2022-0 | AMD EPYC 7763 | scan | 1.0001 [0.9993, 1.0008] | 0.5325 [0.5319, 0.5329] |
| windows-2022-0 | AMD EPYC 7763 | builder | 1.0431 [1.0417, 1.0447] | 0.7724 [0.7710, 0.7738] |
| windows-2022-0 | AMD EPYC 7763 | immutable | 1.0057 [1.0031, 1.0072] | 49.9882 [49.8124, 50.0989] |
| windows-2022-1 | AMD EPYC 7763 | lcg | 0.9998 [0.9984, 1.0002] | 1.8582 [1.8561, 1.8601] |
| windows-2022-1 | AMD EPYC 7763 | primes | 1.0562 [1.0523, 1.0599] | 1.2377 [1.2336, 1.2401] |
| windows-2022-1 | AMD EPYC 7763 | scan | 0.9998 [0.9990, 1.0005] | 0.5329 [0.5325, 0.5332] |
| windows-2022-1 | AMD EPYC 7763 | builder | 1.0430 [1.0407, 1.0448] | 0.7718 [0.7703, 0.7742] |
| windows-2022-1 | AMD EPYC 7763 | immutable | 1.0054 [1.0030, 1.0076] | 50.4741 [50.0168, 50.7262] |

The same Linux OS produced prime throughput ratios of about 0.80 on AMD EPYC 7763 and 1.21 on Intel Xeon Platinum 8573C, so hardware/toolchain variation matters independently of OS. On Windows EPYC, primes gain about 5.6%, versus the larger developer-machine improvement, while scan and builder are about 0.53 and 0.77 of Rust throughput. On virtual Apple M1, the prime lowering regresses and multiple other rows miss 1.10. These results **disprove a blanket cross-OS similarity claim for the current compiler**. Different CPUs and C/Rust toolchains prevent attribution of the difference to OS alone.

## Reserved-buffer experiment and review

The `reserved-builder` generated-C prototype validates a fresh builder's live data, zero length and `cap > n` once, emits the same wrapping byte expression into the cached buffer, commits length after all iterations and calls unchanged `finish_take`. Otherwise it executes the original checked loop. It does not change the shipped compiler. A 12-group local smoke passed 120 direct reference checks, 180 prewarms and 180 measured executions; its builder ratio was 1.3483 [1.2767,1.6565] versus old Forge and 1.4205 [1.3061,1.6692] versus Rust. The local machine in that report is AMD BC-250, and wide intervals in other rows prevent treating it as a final suite result.

OMO worker `ses_ecce1af5bffelUJqkHCnD5cHJ5` reviewed the abstract proof read-only. Its useful obligations are no builder escape or observers, no mutation/reset/calls inside the pure loop, one-byte append semantics, defined wrapping arithmetic, exactly n iterations, spare terminator capacity and fallback preservation. The actual builder-char implementation appends one byte and writes its terminator at finish. The worker's assertion that a terminator per append would make `cap >= n+1` insufficient is incorrect: even that extra store fits; observer equivalence would still require analysis. Its suggestion that shared undefined overflow is acceptable is also rejected: `FORGE_ADD` must provide defined wrapping semantics. The candidate uses it for i+seed; the loop index cannot overflow because it increments only while 0 <= i < n <= INT64_MAX. For every signed seed, truncating remainder by 26 is in -25..25, hence emitted bytes are 40..90 and nonzero. A generic compiler lowering must prove the full conditions rather than assume them.

Full 60-group independent cross-OS prototype matrices were dispatched as [reserved-builder 38338169330](https://github.com/forge-language/forge-benchmarks/actions/runs/38338169330) and [hardware-builder 38338361083](https://github.com/forge-language/forge-benchmarks/actions/runs/38338361083). The latter also exercises the original checked hardware remainder instead of reciprocal caching. Both matrices completed successfully. Reserved-builder gains were 2.16–2.28× old Forge on macOS, 1.21–1.27× on Linux and 1.24–1.25× on Windows; all six lower interval bounds exceed 1.10. Windows builder still misses Rust 1.10. Hardware-builder restores macOS primes to about old Forge but only ~0.95× Rust. Full rows and the guarded compiler integration `d4c632b` appear in [the lowering report](reserved-builder-lowering-2026-10-13.md). The actual compiler verification run 38339445212 completed all six jobs; prototype evidence remains separate. Its unmodified compiler results follow.

## Actual compiler `d4c632b` verification

[Run 38339445212](https://github.com/forge-language/forge-benchmarks/actions/runs/38339445212) uses the integrated reserved-builder lowering, with no generated-C modification. All six native jobs passed 120 direct checks, 900 prewarms and 900 measured executions each; Windows API regression checks also passed. Both Forge programs use the same per-run SDK archives/headers and unchanged matched workload sources.

| Platform / repeat | CPU | Workload | Candidate / old Forge (95% interval) | Candidate / Rust (95% interval) |
| --- | --- | --- | ---: | ---: |
| macos-15-0 | Apple M1 (Virtual) | lcg | 1.0333 [1.0077,1.0637] | 0.8675 [0.8440,0.8936] |
| macos-15-0 | Apple M1 (Virtual) | primes | 0.7378 [0.7303,0.7458] | 0.7092 [0.7014,0.7156] |
| macos-15-0 | Apple M1 (Virtual) | scan | 0.9807 [0.9359,1.0047] | 0.9530 [0.9274,0.9949] |
| macos-15-0 | Apple M1 (Virtual) | builder | 2.2491 [2.0764,2.3659] | 1.3518 [1.2449,1.4194] |
| macos-15-0 | Apple M1 (Virtual) | immutable | 0.9980 [0.9842,1.0069] | 18.9938 [17.1311,19.7786] |
| macos-15-1 | Apple M1 (Virtual) | lcg | 0.9982 [0.9904,1.0109] | 0.8779 [0.8643,0.8859] |
| macos-15-1 | Apple M1 (Virtual) | primes | 0.7360 [0.7323,0.7429] | 0.7056 [0.7001,0.7150] |
| macos-15-1 | Apple M1 (Virtual) | scan | 0.9964 [0.9933,1.0025] | 1.0005 [0.9946,1.0053] |
| macos-15-1 | Apple M1 (Virtual) | builder | 2.2830 [2.2795,2.2901] | 1.3050 [1.3021,1.3076] |
| macos-15-1 | Apple M1 (Virtual) | immutable | 1.0031 [0.9988,1.0108] | 16.5934 [16.4966,16.7364] |
| ubuntu-24.04-0 | AMD EPYC 7763 | lcg | 0.9999 [0.9995,1.0002] | 1.8553 [1.8544,1.8563] |
| ubuntu-24.04-0 | AMD EPYC 7763 | primes | 0.7999 [0.7993,0.8016] | 1.0111 [1.0085,1.0123] |
| ubuntu-24.04-0 | AMD EPYC 7763 | scan | 1.0135 [1.0129,1.0151] | 0.9221 [0.9208,0.9233] |
| ubuntu-24.04-0 | AMD EPYC 7763 | builder | 1.2678 [1.2652,1.2695] | 1.1917 [1.1902,1.1929] |
| ubuntu-24.04-0 | AMD EPYC 7763 | immutable | 1.0015 [0.9984,1.0036] | 22.5728 [22.4347,22.6016] |
| ubuntu-24.04-1 | see hardware record | lcg | 0.9990 [0.9939,1.0020] | 1.6212 [1.6171,1.6260] |
| ubuntu-24.04-1 | see hardware record | primes | 0.9367 [0.9349,0.9387] | 1.1314 [1.1267,1.1359] |
| ubuntu-24.04-1 | see hardware record | scan | 1.0057 [1.0003,1.0080] | 0.8090 [0.8050,0.8128] |
| ubuntu-24.04-1 | see hardware record | builder | 1.2942 [1.2901,1.2989] | 1.2240 [1.2190,1.2293] |
| ubuntu-24.04-1 | see hardware record | immutable | 0.9989 [0.9966,1.0005] | 18.8358 [18.6985,18.9137] |
| windows-2022-0 | AMD EPYC 7763 | lcg | 0.9996 [0.9990,1.0002] | 1.8579 [1.8562,1.8595] |
| windows-2022-0 | AMD EPYC 7763 | primes | 1.0594 [1.0583,1.0621] | 1.2456 [1.2439,1.2468] |
| windows-2022-0 | AMD EPYC 7763 | scan | 1.0000 [0.9991,1.0006] | 0.5327 [0.5324,0.5330] |
| windows-2022-0 | AMD EPYC 7763 | builder | 1.2953 [1.2935,1.2987] | 0.9585 [0.9574,0.9611] |
| windows-2022-0 | AMD EPYC 7763 | immutable | 1.0067 [1.0053,1.0083] | 50.4061 [50.0975,50.6247] |
| windows-2022-1 | see hardware record | lcg | 1.0011 [0.9972,1.0028] | 1.6285 [1.6231,1.6345] |
| windows-2022-1 | see hardware record | primes | 1.0809 [1.0753,1.0861] | 1.3544 [1.3488,1.3579] |
| windows-2022-1 | see hardware record | scan | 0.9958 [0.9922,0.9997] | 0.3867 [0.3848,0.3897] |
| windows-2022-1 | see hardware record | builder | 1.1868 [1.1840,1.1897] | 0.8712 [0.8682,0.8735] |
| windows-2022-1 | see hardware record | immutable | 1.0009 [0.9978,1.0031] | 53.9900 [53.5330,54.2429] |

**A similar positive builder effect is now established on the three tested OSes**, relative to each runner's old Forge baseline: Linux 1.27–1.29×, macOS 2.25–2.28× and Windows 1.19–1.30×. All six lower row-wise interval bounds exceed 1.10. This is a workload-specific before/after conclusion. Windows builder still falls below Rust and macOS primes still regress; the overall Rust 1.10 / cross-OS suite goal remains unachieved. CPU/toolchain differences confound OS-only causal interpretations.

## Sources and preserved evidence

Windows API behavior was checked against [Microsoft MoveFileEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexa), [QPC](https://learn.microsoft.com/en-us/windows/win32/api/profileapi/nf-profileapi-queryperformancecounter), and the [MinGW stat declarations](https://raw.githubusercontent.com/mingw-w64/mingw-w64/master/mingw-w64-headers/crt/sys/stat.h). The [runner documentation](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) distinguishes x86 Linux/Windows and ARM64 macOS hosted hardware.

All workload rows, checks, warmups, raw samples, flags, generated-C/source/binary hashes and runner source remain in the individual JSON files listed by [the attempt ledger](cross-os-attempts-2026-10-13.json). [The OMO review](cross-os-omo-review-2026-10-13.md) has a narrower scope than the executable pipeline and includes explicit limitations. No failure is dropped to improve the reported result.

Frozen inputs, executables, assembly and failure logs are preserved in [the first five matrices archive](cross-os-first-five-matrices-2026-10-13.raw.tar.gz) and [the native follow-up archive](cross-os-followup-native-2026-10-13.raw.tar.gz). Archive hashes are recorded in `cross-os-archives-2026-10-13.sha256`.

The integrated compiler matrix is frozen in [its native archive](cross-os-reserved-compiler-2026-10-13.raw.tar.gz). The screening matrices remain in [the separate prototype archive](cross-os-reserved-probes-2026-10-13.raw.tar.gz).

The subsequent generated-C [range-kernel screening](range-kernels-cross-os-2026-10-13.md) adds a macOS LCG gain but still fails prime/scan thresholds and is retained as a partially useful experiment, not a compiler release.

The generated-C [current-control periodic scan report](hybrid-range-cross-os-2026-10-13.md) demonstrates a strong scan/builder improvement in every native job, while macOS prime still misses Rust 1.10. It remains a prototype awaiting general compiler integration.

The [actual Mersenne loop lowering](mersenne-loop-cross-os-2026-10-13.md) reproduces the Apple M1 LCG improvement. The [word-size arithmetic variant](precision-range-cross-os-2026-10-13.md) worsens macOS primes and is rejected. The final integrated periodic-sum/ARM64-policy compiler verification run38352449216 completed; [its unchanged-compiler results](integrated-compiler-cross-os-2026-10-13.md) demonstrate scan/builder gains on all three tested OSes, while prime misses remain.
