# Reserved-builder loop lowering: proof and native measurements

Compiler commit `d4c632b59e215806944a74fa3e80aea7752a5bba` preserves the public builder API and Forge wrapping arithmetic. The native backend now recognizes a fresh local `str_builder_with_capacity(n)`, an optional immediate zero-handle return guard, a zero index, and an immediate `while(i<n)` containing exactly a checked byte append and a unit index increment. It requires a known integer bound and pure integer byte syntax with a proven 1..127 range. Calls, aliases, observers, writes, extra control flow, shadowed locals, dynamic division and coroutine storage fail closed. Matching uses the imported standard API and rejects user function overrides; the expression walk shares the bounded function proof budget.

An entry guard checks a nonzero builder, positive n, live data, len zero and cap greater than n. Passing implies all n byte writes plus the final terminator fit, every byte is valid, and the original checked append cannot grow or fail. The private builder cannot be observed during the loop. The generated loop writes the same byte expression and performs the same n index increments, then commits len. All other cases execute the original checked loop. Later builder reuse and the existing finish API see identical buffer contents, index, data pointer, length and capacity. Allocation count and lifetime remain unchanged in the fast path; the fallback retains failure behavior.

The range proof operates on defined Forge integer wrapping. For the measured expression `65+(i+seed)%26`, signed truncating remainder is in -25..25, so every signed seed, including wrapping sums, gives bytes 40..90. The guard also proves 0<=i<n<=INT64_MAX, so the plain index increment cannot overflow. On a narrower size_t target, cap>n excludes any bound that cannot fit; the length cast is safe.

## Verification

All 22 Linux CTest suites passed after a full build. The new arithmetic oracle checks 36 dimension/seed combinations at -O0/-O3 under UBSan, both inline and ABI-only string headers, and JavaScript. It verifies exact bytes and the final index. A controlled constructor seam exercises zero handles, an empty builder, cap exactly n (growth fallback), and an existing prefix (length fallback), using the real append and finish implementations. Matcher regressions reject 12 unproven shapes and check generated-name collisions. These checks establish the narrow lowering contract; no claim covers arbitrary external ABI interposition or malformed fabricated handles.

The prior abstract OMO review is corrected in the cross-OS report. The same delegated Sisyphus-Junior worker completed an implementation inspection against the current pinned SDK and compiler patch and found no correctness/security blockers within the stated contract. An intervening CLI continuation selected the primary agent and read an obsolete dependency checkout; it was stopped and corrected with exact source paths. The [implementation review](reserved-builder-omo-implementation-review-2026-10-13.md) preserves that scope, the full history and explicit corrections. The proof does not rely on an assumption that an enormous allocation must fail.

## Generated-C screening experiments

These rows were measured before compiler integration, at shipped compiler `12d8ff4` with explicit generated-C changes. They screen the transformation but are not measurements of compiler `d4c632b`.

| Run / platform / repeat | Experiment | Builder / old Forge (95% interval) | Builder / Rust (95% interval) |
| --- | --- | ---: | ---: |
| [38338169330](https://github.com/forge-language/forge-benchmarks/actions/runs/38338169330) / macos-15-0 | reserved-builder | 2.2805 [2.2673,2.2953] | 1.3062 [1.2976,1.3102] |
| [38338169330](https://github.com/forge-language/forge-benchmarks/actions/runs/38338169330) / macos-15-1 | reserved-builder | 2.1587 [2.0580,2.2906] | 1.2867 [1.2256,1.3335] |
| [38338169330](https://github.com/forge-language/forge-benchmarks/actions/runs/38338169330) / ubuntu-24.04-0 | reserved-builder | 1.2677 [1.2669,1.2691] | 1.1924 [1.1915,1.1933] |
| [38338169330](https://github.com/forge-language/forge-benchmarks/actions/runs/38338169330) / ubuntu-24.04-1 | reserved-builder | 1.2094 [1.2071,1.2106] | 1.3193 [1.3178,1.3209] |
| [38338169330](https://github.com/forge-language/forge-benchmarks/actions/runs/38338169330) / windows-2022-0 | reserved-builder | 1.2419 [1.2379,1.2499] | 0.9305 [0.9280,0.9365] |
| [38338169330](https://github.com/forge-language/forge-benchmarks/actions/runs/38338169330) / windows-2022-1 | reserved-builder | 1.2511 [1.2432,1.2571] | 0.9354 [0.9333,0.9380] |
| [38338361083](https://github.com/forge-language/forge-benchmarks/actions/runs/38338361083) / macos-15-0 | hardware-builder | 2.3111 [2.2698,2.3558] | 1.3231 [1.3015,1.3399] |
| [38338361083](https://github.com/forge-language/forge-benchmarks/actions/runs/38338361083) / macos-15-1 | hardware-builder | 2.2723 [2.1582,2.3152] | 1.3018 [1.2548,1.3310] |
| [38338361083](https://github.com/forge-language/forge-benchmarks/actions/runs/38338361083) / ubuntu-24.04-0 | hardware-builder | 1.2922 [1.2904,1.2934] | 1.2217 [1.2203,1.2231] |
| [38338361083](https://github.com/forge-language/forge-benchmarks/actions/runs/38338361083) / ubuntu-24.04-1 | hardware-builder | 1.3978 [1.3942,1.3995] | 1.3144 [1.3127,1.3166] |
| [38338361083](https://github.com/forge-language/forge-benchmarks/actions/runs/38338361083) / windows-2022-0 | hardware-builder | 1.2963 [1.2946,1.2993] | 0.9604 [0.9591,0.9631] |
| [38338361083](https://github.com/forge-language/forge-benchmarks/actions/runs/38338361083) / windows-2022-1 | hardware-builder | 1.2952 [1.2930,1.2994] | 0.9615 [0.9595,0.9636] |

Every reserved-builder row improves old Forge with a lower interval bound above 1.10, across all three OSes. macOS and Linux builder rows exceed Rust 1.10; Windows builder still misses Rust 1.10. Other workloads retain their measured failures. The hardware-builder experiment restores macOS prime throughput to roughly old Forge, but only about 0.95 of Rust. It is not adopted by this compiler commit.

## Unmodified compiler evidence

The local AMD BC-250 60-group run measures compiler `d4c632b` unchanged: builder/old Forge 1.3944 [1.2951,1.5511]; builder/Rust 1.4777 [1.3972,1.5868]. It passed 21 direct oracle checks, 180 prewarms and 180 measurements. The [raw report](reserved-builder-compiler-60-2026-10-13.json) preserves inputs, SDK/compiler/source hashes, flags and all observations. It supports this case on this machine, not every OS or every workload.

The final unchanged-compiler three-OS verification [run 38339445212](https://github.com/forge-language/forge-benchmarks/actions/runs/38339445212) completed all six jobs. Compiler `d4c632b` was freshly built on each native runner with no generated-C patch. Every job passed 120 direct oracle checks, 900 prewarms and 900 measured executions (720/5400/5400 across the matrix). Windows temporary-file and filesystem tests also passed.

| Platform / repeat | CPU | Builder / old Forge (95% interval) | Builder / Rust (95% interval) |
| --- | --- | ---: | ---: |
| macos-15-0 | Apple M1 (Virtual) | 2.2491 [2.0764,2.3659] | 1.3518 [1.2449,1.4194] |
| macos-15-1 | Apple M1 (Virtual) | 2.2830 [2.2795,2.2901] | 1.3050 [1.3021,1.3076] |
| ubuntu-24.04-0 | AMD EPYC 7763 | 1.2678 [1.2652,1.2695] | 1.1917 [1.1902,1.1929] |
| ubuntu-24.04-1 | see hardware record | 1.2942 [1.2901,1.2989] | 1.2240 [1.2190,1.2293] |
| windows-2022-0 | AMD EPYC 7763 | 1.2953 [1.2935,1.2987] | 0.9585 [0.9574,0.9611] |
| windows-2022-1 | see hardware record | 1.1868 [1.1840,1.1897] | 0.8712 [0.8682,0.8735] |

The actual compiler's builder lowering improves throughput on every tested OS: Linux 1.27–1.29×, macOS 2.25–2.28× and Windows 1.19–1.30× old Forge. Every row-wise lower 95% bound exceeds 1.10. This establishes a consistent positive effect for this specific private builder workload on the listed native hardware, with different gain sizes. It does **not** establish Rust 1.10 across OSes: Windows builder remains 0.87–0.96× Rust, and other workload misses persist. The full matrix and earlier negative results remain in the [cross-OS report](cross-os-verification-2026-10-13.md). Frozen sources, shared SDK inputs, binaries and assembly are in `cross-os-reserved-compiler-2026-10-13.raw.tar.gz`; the local archive is `reserved-builder-compiler-60-2026-10-13.raw.tar.gz`. Both SHA-256 hashes are recorded in `cross-os-archives-2026-10-13.sha256`.
