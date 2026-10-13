# Native cross-OS CPU comparison

Platform: `Linux-6.8.0-139-generic-x86_64-with-glibc2.39` / `x86_64`. Measured 12 balanced triples per workload, seed 20261013.
**Generated-C experiment `hybrid-range`: the candidate C helper is modified after emission. These results do not measure the shipped compiler unchanged.**


| Workload | Candidate / baseline (95% interval) | Candidate / Rust (95% interval) | Rust 1.10 |
| --- | ---: | ---: | --- |
| lcg | 1.0361 [0.9891, 1.1069] | 1.2858 [1.2529, 1.4253] | supported for this case |
| primes | 1.5182 [1.2523, 1.7715] | 1.9059 [1.5343, 1.9566] | supported for this case |
| scan | 1.6433 [1.3867, 2.6068] | 2.6651 [2.4995, 4.3245] | supported for this case |
| builder | 0.9543 [0.7355, 1.1267] | 1.6843 [1.5203, 1.7543] | supported for this case |
| immutable | 0.9245 [0.5591, 1.3616] | 8.4105 [7.0154, 17.8458] | supported for this case |

All measured checksums and same-input warmups match an independent Python reference. All six three-way permutations occur equally often. Each row has a paired-ratio bootstrap 95% interval; this is not simultaneous confidence over workloads or proof for all programs.

Both Forge versions share identical SDK archives/headers, source algorithms and clock; one Rust control is used throughout. C uses -O3/native CPU tuning/LTO; Rust uses opt-level=3, target-cpu=native, thin LTO and disabled overflow checks. Process startup is excluded from kernel times. All platforms use unpinned child processes; virtualized/shared runners and frequency changes remain sources of noise. Compare before/after ratios within each OS; absolute times across different OS/hardware/architectures are not OS-only causal comparisons.

Builder transfers the buffer in both implementations. Immutable append uses different allocation/lifetime policies. CPU results do not prove HTTP capacity, memory-safety equivalence or universal language throughput. Build failures are recorded as failed_no_claim and must not be silently removed from the cross-OS report.

Full samples, commands and hashes: [hybrid-range-current-smoke-2026-10-13.json](hybrid-range-current-smoke-2026-10-13.json).
