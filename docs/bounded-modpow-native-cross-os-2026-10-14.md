# Unchanged compiler: native Linux, macOS and Windows verification

Run [38513930496](https://github.com/forge-language/forge-benchmarks/actions/runs/38513930496) measures committed compiler `a750b60` with **no generated-C probe**, against original Forge `9f70e9d` and unchanged matched Rust. Runtime `dcbb192` and stdlib `6aa2866` are shared by both Forge producers within each job. Each of six jobs has 60 balanced three-way groups for each of five workloads. All 720 direct correctness cases, 5,400 prewarms and 5,400 measured executions pass independent references. Frozen compiler, archive, header and measured executable hashes were rechecked against the downloaded files. Native Windows temporary-file and filesystem tests also pass in both jobs.

| Native job | Workload | New/original Forge throughput (95% interval) | New Forge/Rust throughput (95% interval) |
| --- | --- | --- | --- |
| [macos-15-0](cross-os-38513930496-macos-15-0.json) | lcg | 1.8831 [1.8169, 1.9203] | 1.6248 [1.6014, 1.6682] |
| [macos-15-0](cross-os-38513930496-macos-15-0.json) | primes | 1.2928 [1.2797, 1.3045] | 1.2321 [1.2249, 1.2391] |
| [macos-15-0](cross-os-38513930496-macos-15-0.json) | scan | 8.8979 [8.7125, 9.1337] | 8.7717 [8.5946, 8.9961] |
| [macos-15-0](cross-os-38513930496-macos-15-0.json) | builder | 5.7175 [5.6817, 5.7638] | 3.2640 [3.2258, 3.3053] |
| [macos-15-0](cross-os-38513930496-macos-15-0.json) | immutable | 1.3234 [1.3133, 1.3524] | 22.6684 [22.3037, 23.2017] |
| [macos-15-1](cross-os-38513930496-macos-15-1.json) | lcg | 1.8366 [1.8142, 1.8927] | 1.6034 [1.5789, 1.6298] |
| [macos-15-1](cross-os-38513930496-macos-15-1.json) | primes | 1.2889 [1.2812, 1.3055] | 1.2235 [1.2124, 1.2369] |
| [macos-15-1](cross-os-38513930496-macos-15-1.json) | scan | 8.9495 [8.8718, 9.1579] | 9.1401 [8.9391, 9.2134] |
| [macos-15-1](cross-os-38513930496-macos-15-1.json) | builder | 5.7625 [5.6800, 5.8099] | 3.3445 [3.2797, 3.3959] |
| [macos-15-1](cross-os-38513930496-macos-15-1.json) | immutable | 1.3418 [1.3258, 1.3535] | 23.5906 [23.1525, 23.9404] |
| [ubuntu-24.04-0](cross-os-38513930496-ubuntu-24.04-0.json) | lcg | 0.9999 [0.9992, 1.0006] | 1.8559 [1.8548, 1.8568] |
| [ubuntu-24.04-0](cross-os-38513930496-ubuntu-24.04-0.json) | primes | 1.0916 [1.0901, 1.0930] | 1.3783 [1.3758, 1.3810] |
| [ubuntu-24.04-0](cross-os-38513930496-ubuntu-24.04-0.json) | scan | 2.6650 [2.6629, 2.6701] | 2.4230 [2.4207, 2.4262] |
| [ubuntu-24.04-0](cross-os-38513930496-ubuntu-24.04-0.json) | builder | 1.6297 [1.6171, 1.6433] | 1.5278 [1.5209, 1.5352] |
| [ubuntu-24.04-0](cross-os-38513930496-ubuntu-24.04-0.json) | immutable | 1.1611 [1.1573, 1.1647] | 26.2088 [26.1447, 26.2599] |
| [ubuntu-24.04-1](cross-os-38513930496-ubuntu-24.04-1.json) | lcg | 1.0001 [0.9997, 1.0004] | 1.8552 [1.8548, 1.8559] |
| [ubuntu-24.04-1](cross-os-38513930496-ubuntu-24.04-1.json) | primes | 1.0901 [1.0880, 1.0914] | 1.3977 [1.3957, 1.4025] |
| [ubuntu-24.04-1](cross-os-38513930496-ubuntu-24.04-1.json) | scan | 5.1560 [5.1366, 5.1667] | 4.8289 [4.8200, 4.8364] |
| [ubuntu-24.04-1](cross-os-38513930496-ubuntu-24.04-1.json) | builder | 1.7536 [1.7494, 1.7566] | 1.9222 [1.9213, 1.9236] |
| [ubuntu-24.04-1](cross-os-38513930496-ubuntu-24.04-1.json) | immutable | 1.2293 [1.2251, 1.2330] | 22.0934 [22.0473, 22.1809] |
| [windows-2022-0](cross-os-38513930496-windows-2022-0.json) | lcg | 0.9998 [0.9992, 1.0002] | 1.8555 [1.8545, 1.8577] |
| [windows-2022-0](cross-os-38513930496-windows-2022-0.json) | primes | 1.1798 [1.1746, 1.1819] | 1.3835 [1.3806, 1.3861] |
| [windows-2022-0](cross-os-38513930496-windows-2022-0.json) | scan | 4.4147 [4.4116, 4.4193] | 2.3562 [2.3526, 2.3598] |
| [windows-2022-0](cross-os-38513930496-windows-2022-0.json) | builder | 2.0946 [2.0906, 2.0988] | 1.5512 [1.5497, 1.5534] |
| [windows-2022-0](cross-os-38513930496-windows-2022-0.json) | immutable | 1.5624 [1.5592, 1.5666] | 77.5570 [77.0937, 77.8725] |
| [windows-2022-1](cross-os-38513930496-windows-2022-1.json) | lcg | 0.9939 [0.9932, 0.9943] | 1.6624 [1.6614, 1.6632] |
| [windows-2022-1](cross-os-38513930496-windows-2022-1.json) | primes | 1.6815 [1.6771, 1.6881] | 1.8716 [1.8687, 1.8770] |
| [windows-2022-1](cross-os-38513930496-windows-2022-1.json) | scan | 3.3674 [3.3621, 3.3709] | 2.1952 [2.1872, 2.2293] |
| [windows-2022-1](cross-os-38513930496-windows-2022-1.json) | builder | 1.8498 [1.8460, 1.8527] | 1.3785 [1.3760, 1.3811] |
| [windows-2022-1](cross-os-38513930496-windows-2022-1.json) | immutable | 1.1968 [1.1892, 1.2085] | 84.7338 [84.0134, 85.2823] |

**All 30 measured Forge/Rust row-wise lower 95% bounds exceed 1.10.** Native prime/Rust medians are Linux 1.378–1.398×, macOS 1.224–1.232× and Windows 1.384–1.872×. Together with the [local unchanged-compiler suite](bounded-modpow-generic-full-60-2026-10-14.md), this verifies the representative five-workload target on the tested native systems. These are individual bootstrap intervals, not a simultaneous family-wise confidence statement, a language-wide guarantee, or a guarantee on future machines. The interval minimum is about 1.2124.

The native effect is positive for the implemented private builder, periodic scan and bounded exponentiation workloads, but not every workload improves old Forge by 10% and LCG can be unchanged. Every row is retained. OS, CPU, virtualization, compiler versions and optimization decisions differ, so the data establish behavior on the tested OS/CPU/toolchain combinations rather than isolate OS causality. Compiler source revisions are fixed; fresh Windows producer binaries can have different hashes and fresh macOS SDK archives can vary across jobs. Inputs are shared within each comparison, not asserted byte-identical across jobs/platforms.

The exact frozen dimensions source is now included. The differing Windows dimension hashes are verified as CRLF versions of the same canonical LF JSON, not assumed equivalent without a check. The matching reference source, seeded inputs, timer object, flags, disassembly and original/candidate/Rust executables are retained. No excluded failures, timing-outlier trimming or silent retries were used.

The [attempt ledger](cross-os-attempts-2026-10-13.json) contains 19 runs and 106 jobs (92 successful, 14 failed), with 96 reports (92 completed, four failed_no_claim). Failed infrastructure and rejected prototype attempts remain visible. The [generic implementation proof and six OMO reviews](bounded-modpow-lowering-2026-10-14.md) are independent of this performance evidence.

**HTTP maximum users remain unestablished.** The [Linux V3.3 HTTP observation](http-v33-observed-128k-2026-10-13.md) completed 128,000 requests in every trial, but recorded only 512–576 Forge in-flight states and 260–320 connected client states. Median throughput was 2,860 req/s and the paired interval was inconclusive. Those state counts do not count accepted server sessions or users. HTTP was not benchmarked on macOS/Windows and is not covered by these CPU conclusions.

[All native sources, commands, binaries, disassembly and canonical dimension inputs](bounded-modpow-native-cross-os-2026-10-14.raw.tar.gz), SHA-256 `ecbf1e42f83e692d27cc2810fe325891cf6ce71bbb58ffb62e9d678a289fbd93`.
