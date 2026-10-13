# Cross-OS verification: measured regressions and remaining work

Status: **not achieved**. Linux developer-machine gains are not evidence of the same effect on another OS. Eight hosted-runner attempts preserve 26 completed CPU reports, four failed-before-measurement reports and all 40 job outcomes (26 successes, 14 failures). Native Windows measurement now completed twice, but scan and builder remain below Rust and the macOS prime regression persists.

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

## Latest unchanged-compiler results

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

Full 60-group independent cross-OS prototype matrices were dispatched as [reserved-builder 38338169330](https://github.com/forge-language/forge-benchmarks/actions/runs/38338169330) and [hardware-builder 38338361083](https://github.com/forge-language/forge-benchmarks/actions/runs/38338361083). The latter also exercises the original checked hardware remainder instead of reciprocal caching. Their results are pending at this checkpoint and must remain separate from unchanged shipped-compiler evidence.

## Sources and preserved evidence

Windows API behavior was checked against [Microsoft MoveFileEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexa), [QPC](https://learn.microsoft.com/en-us/windows/win32/api/profileapi/nf-profileapi-queryperformancecounter), and the [MinGW stat declarations](https://raw.githubusercontent.com/mingw-w64/mingw-w64/master/mingw-w64-headers/crt/sys/stat.h). The [runner documentation](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) distinguishes x86 Linux/Windows and ARM64 macOS hosted hardware.

All workload rows, checks, warmups, raw samples, flags, generated-C/source/binary hashes and runner source remain in the individual JSON files listed by [the attempt ledger](cross-os-attempts-2026-10-13.json). [The OMO review](cross-os-omo-review-2026-10-13.md) has a narrower scope than the executable pipeline and includes explicit limitations. No failure is dropped to improve the reported result.

Frozen inputs, executables, assembly and failure logs are preserved in [the first five matrices archive](cross-os-first-five-matrices-2026-10-13.raw.tar.gz) and [the native follow-up archive](cross-os-followup-native-2026-10-13.raw.tar.gz). Archive hashes are recorded in `cross-os-archives-2026-10-13.sha256`.
