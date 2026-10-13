# Reserved-builder loop lowering: proof and native measurements

Compiler commit `d4c632b59e215806944a74fa3e80aea7752a5bba` preserves the public builder API and Forge wrapping arithmetic. The native backend now recognizes a fresh local `str_builder_with_capacity(n)`, an optional immediate zero-handle return guard, a zero index, and an immediate `while(i<n)` containing exactly a checked byte append and a unit index increment. It requires a known integer bound and pure integer byte syntax with a proven 1..127 range. Calls, aliases, observers, writes, extra control flow, shadowed locals, dynamic division and coroutine storage fail closed. Matching uses the imported standard API and rejects user function overrides; the expression walk shares the bounded function proof budget.

An entry guard checks a nonzero builder, positive n, live data, len zero and cap greater than n. Passing implies all n byte writes plus the final terminator fit, every byte is valid, and the original checked append cannot grow or fail. The private builder cannot be observed during the loop. The generated loop writes the same byte expression and performs the same n index increments, then commits len. All other cases execute the original checked loop. Later builder reuse and the existing finish API see identical buffer contents, index, data pointer, length and capacity. Allocation count and lifetime remain unchanged in the fast path; the fallback retains failure behavior.

The range proof operates on defined Forge integer wrapping. For the measured expression `65+(i+seed)%26`, signed truncating remainder is in -25..25, so every signed seed, including wrapping sums, gives bytes 40..90. The guard also proves 0<=i<n<=INT64_MAX, so the plain index increment cannot overflow. On a narrower size_t target, cap>n excludes any bound that cannot fit; the length cast is safe.

## Verification

All 22 Linux CTest suites passed after a full build. The new arithmetic oracle checks 36 dimension/seed combinations at -O0/-O3 under UBSan, both inline and ABI-only string headers, and JavaScript. It verifies exact bytes and the final index. A controlled constructor seam exercises zero handles, an empty builder, cap exactly n (growth fallback), and an existing prefix (length fallback), using the real append and finish implementations. Matcher regressions reject 12 unproven shapes and check generated-name collisions. These checks establish the narrow lowering contract; no claim covers arbitrary external ABI interposition or malformed fabricated handles.

The prior abstract OMO review is corrected in the cross-OS report. The implementation review continued the same delegated session through the CLI, which selected the primary agent for that continuation; its final findings are pending at this checkpoint. Do not treat that unfinished continuation as a completed independent implementation review.

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

The final unchanged-compiler three-OS verification [run 38339445212](https://github.com/forge-language/forge-benchmarks/actions/runs/38339445212) is running at this checkpoint. Only those completed reports can establish that the actual compiler reproduces the cross-OS screening gains.
