# Target remainder policy: native rejected screening

Run [38356215316](https://github.com/forge-language/forge-benchmarks/actions/runs/38356215316) completed all six native jobs. The benchmark compiler producer and baseline are both shipped Forge `420d66f`; only the explicitly labeled candidate generated C changes. It disables invariant reciprocal on `__znver3__` and adds an ARM64 false-branch hint to the pure power predicate. The Rust fixtures, algorithms, SDK and native build flags are unchanged. Each job uses 60 balanced three-way groups per workload; all 720 direct correctness, 5,400 prewarm and 5,400 measured executions match independent references.

| Native job | Workload | Candidate/current Forge ratio (95% interval) | Candidate/Rust ratio (95% interval) | Target |
| --- | --- | --- | --- | --- |
| [macos-15-0](cross-os-38356215316-macos-15-0.json) | lcg | 1.0037 [0.9680, 1.0497] | 1.6433 [1.5975, 1.7093] | supported for this case |
| [macos-15-0](cross-os-38356215316-macos-15-0.json) | primes | 1.0023 [0.9852, 1.0304] | 0.9485 [0.9215, 0.9776] | below target |
| [macos-15-0](cross-os-38356215316-macos-15-0.json) | scan | 1.0049 [0.9761, 1.0236] | 9.2049 [8.8776, 9.4621] | supported for this case |
| [macos-15-0](cross-os-38356215316-macos-15-0.json) | builder | 1.0121 [0.9498, 1.1180] | 3.3379 [3.1555, 3.4516] | supported for this case |
| [macos-15-0](cross-os-38356215316-macos-15-0.json) | immutable | 1.0031 [0.9658, 1.0472] | 27.2222 [26.4383, 28.4721] | supported for this case |
| [macos-15-1](cross-os-38356215316-macos-15-1.json) | lcg | 0.9981 [0.9944, 1.0050] | 1.6045 [1.5869, 1.6145] | supported for this case |
| [macos-15-1](cross-os-38356215316-macos-15-1.json) | primes | 1.0009 [0.9936, 1.0059] | 0.9549 [0.9513, 0.9655] | below target |
| [macos-15-1](cross-os-38356215316-macos-15-1.json) | scan | 1.0012 [0.9971, 1.0089] | 9.0316 [8.9442, 9.1847] | supported for this case |
| [macos-15-1](cross-os-38356215316-macos-15-1.json) | builder | 0.9999 [0.9942, 1.0050] | 3.3484 [3.3204, 3.4431] | supported for this case |
| [macos-15-1](cross-os-38356215316-macos-15-1.json) | immutable | 0.9995 [0.9948, 1.0020] | 22.3658 [22.2441, 22.4935] | supported for this case |
| [ubuntu-24.04-0](cross-os-38356215316-ubuntu-24.04-0.json) | lcg | 1.0001 [0.9998, 1.0003] | 1.8554 [1.8551, 1.8556] | supported for this case |
| [ubuntu-24.04-0](cross-os-38356215316-ubuntu-24.04-0.json) | primes | 1.0000 [0.9992, 1.0009] | 1.0162 [1.0139, 1.0176] | below target |
| [ubuntu-24.04-0](cross-os-38356215316-ubuntu-24.04-0.json) | scan | 1.0013 [0.9903, 1.0089] | 2.4151 [2.3897, 2.4425] | supported for this case |
| [ubuntu-24.04-0](cross-os-38356215316-ubuntu-24.04-0.json) | builder | 0.9998 [0.9977, 1.0014] | 1.7189 [1.7166, 1.7221] | supported for this case |
| [ubuntu-24.04-0](cross-os-38356215316-ubuntu-24.04-0.json) | immutable | 0.9983 [0.9959, 1.0015] | 21.7946 [21.7120, 21.8239] | supported for this case |
| [ubuntu-24.04-1](cross-os-38356215316-ubuntu-24.04-1.json) | lcg | 1.0002 [0.9993, 1.0010] | 1.7177 [1.7160, 1.7191] | supported for this case |
| [ubuntu-24.04-1](cross-os-38356215316-ubuntu-24.04-1.json) | primes | 1.0007 [0.9978, 1.0017] | 1.4224 [1.4185, 1.4253] | supported for this case |
| [ubuntu-24.04-1](cross-os-38356215316-ubuntu-24.04-1.json) | scan | 1.0002 [0.9993, 1.0014] | 2.3951 [2.3839, 2.4031] | supported for this case |
| [ubuntu-24.04-1](cross-os-38356215316-ubuntu-24.04-1.json) | builder | 1.0007 [0.9991, 1.0018] | 1.4707 [1.4679, 1.4735] | supported for this case |
| [ubuntu-24.04-1](cross-os-38356215316-ubuntu-24.04-1.json) | immutable | 1.0024 [0.9950, 1.0172] | 24.2186 [24.0241, 24.5854] | supported for this case |
| [windows-2022-0](cross-os-38356215316-windows-2022-0.json) | lcg | 1.0006 [0.9998, 1.0012] | 1.8583 [1.8575, 1.8596] | supported for this case |
| [windows-2022-0](cross-os-38356215316-windows-2022-0.json) | primes | 0.9456 [0.9437, 0.9482] | 1.1833 [1.1789, 1.1845] | supported for this case |
| [windows-2022-0](cross-os-38356215316-windows-2022-0.json) | scan | 0.9999 [0.9990, 1.0008] | 2.3525 [2.3504, 2.3548] | supported for this case |
| [windows-2022-0](cross-os-38356215316-windows-2022-0.json) | builder | 1.0058 [1.0038, 1.0079] | 1.5516 [1.5500, 1.5536] | supported for this case |
| [windows-2022-0](cross-os-38356215316-windows-2022-0.json) | immutable | 0.9994 [0.9973, 1.0008] | 77.8803 [77.3972, 78.2312] | supported for this case |
| [windows-2022-1](cross-os-38356215316-windows-2022-1.json) | lcg | 0.9999 [0.9968, 1.0044] | 1.6229 [1.6198, 1.6282] | supported for this case |
| [windows-2022-1](cross-os-38356215316-windows-2022-1.json) | primes | 1.0009 [0.9976, 1.0053] | 1.3360 [1.3315, 1.3421] | supported for this case |
| [windows-2022-1](cross-os-38356215316-windows-2022-1.json) | scan | 1.0013 [0.9937, 1.0047] | 4.1506 [4.1196, 4.2294] | supported for this case |
| [windows-2022-1](cross-os-38356215316-windows-2022-1.json) | builder | 1.0025 [0.9992, 1.0114] | 1.5878 [1.5806, 1.5951] | supported for this case |
| [windows-2022-1](cross-os-38356215316-windows-2022-1.json) | immutable | 0.9990 [0.9958, 1.0045] | 80.7883 [80.2933, 81.3283] | supported for this case |

The ARM64 branch hint does not establish a speedup: macOS prime candidate/current ratios are about 1.0023 and 1.0009 with intervals including no change; candidate/Rust remains about 0.949–0.955. Its emitted prime division/selection instruction sequence remains the same. The compiler is free to ignore or transform the hint, and the hint does not prove a branch frequency.

The Windows run exposing `__znver3__` regresses prime to 0.9456× current Forge [0.9437, 0.9482], although still above Rust. The Linux AMD EPYC 9V74 run exposes no selected policy macro and produces byte-identical before/after executables; its prime remains about 1.0162× Rust. This is a control result, not evidence for disabling reciprocal on that CPU. CPU model and exposed compiler macros are captured separately. **Neither change is adopted in the shipped compiler.**

Read-only OMO child `ses_ecce1af5bffelUJqkHCnD5cHJ5` found no arithmetic or counter blocker but highlighted branch-hint frequency/performance uncertainty. Its early HTTP-error explanation requires correction: begin-request errors and errors inside the per-request io::Result closure become retained failure rows and can still print a footer; only outer reactor/output failures abort main. The actual phase/counter transitions preserve balance, including Setup being entered before a fallible setup call. The complete review is preserved without silently editing its claims.

Independent signed/wrapping/trap validation passed 671 cases for original/candidate at O0/O3 UBSan under both forced Zen 3 and ARM macros: 5,368 executions. Those are local semantic tests, not native target speed proofs. The [exact test source at the tested revision](target-remainder-oracle-source-2026-10-13.py) retains its original 671-case bounds, before the later 713-case extension. The ARM stdout log is archived; the completed Zen 3 tool stdout is retained in an explicitly labeled transcribed result record, with its command and source hash. Native Windows temp/fs tests also pass in both jobs.

[All native generated C, binaries, disassembly and validation/review evidence](target-remainder-cross-os-2026-10-13.raw.tar.gz), SHA-256 `22f5650086b2c8afd15a0c8199d164896a9562340ab052da006bdbe39d398d96`. At publication, the [attempt ledger](cross-os-attempts-2026-10-13.json) snapshot contained 17 runs, 94 jobs (80 successful, 14 failed) and 84 reports (80 completed, four failed_no_claim); later runs are retained in the current ledger. The unrelated [shipped compiler cross-OS improvements](integrated-compiler-cross-os-2026-10-13.md) remain valid; the all-platform Rust 1.10 suite remains unachieved.
