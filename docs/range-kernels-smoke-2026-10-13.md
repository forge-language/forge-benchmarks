# Native cross-OS CPU comparison

Platform: `Linux-6.8.0-139-generic-x86_64-with-glibc2.39` / `x86_64`. Measured 12 balanced triples per workload, seed 20261013.
**Generated-C experiment `range-kernels`: the candidate C helper is modified after emission. These results do not measure the shipped compiler unchanged.**


| Workload | Candidate / baseline (95% interval) | Candidate / Rust (95% interval) | Rust 1.10 |
| --- | ---: | ---: | --- |
| lcg | 1.0077 [0.9605, 1.0276] | 1.3050 [1.2470, 1.4131] | supported for this case |
| primes | 0.9745 [0.8624, 1.0561] | 0.9556 [0.8093, 1.0440] | below target |
| scan | 1.0103 [0.8329, 1.0518] | 1.4252 [1.1965, 1.5858] | supported for this case |
| builder | 1.2448 [1.1118, 1.4126] | 1.4246 [1.3794, 1.5449] | supported for this case |
| immutable | 0.9074 [0.8199, 1.2384] | 6.9161 [6.5300, 8.2077] | supported for this case |

All measured checksums and same-input warmups match an independent Python reference. All six three-way permutations occur equally often. Each row has a paired-ratio bootstrap 95% interval; this is not simultaneous confidence over workloads or proof for all programs.

Both Forge versions share identical SDK archives/headers, source algorithms and clock; one Rust control is used throughout. C uses -O3/native CPU tuning/LTO; Rust uses opt-level=3, target-cpu=native, thin LTO and disabled overflow checks. Process startup is excluded from kernel times. All platforms use unpinned child processes; virtualized/shared runners and frequency changes remain sources of noise. Compare before/after ratios within each OS; absolute times across different OS/hardware/architectures are not OS-only causal comparisons.

Builder transfers the buffer in both implementations. Immutable append uses different allocation/lifetime policies. CPU results do not prove HTTP capacity, memory-safety equivalence or universal language throughput. Build failures are recorded as failed_no_claim and must not be silently removed from the cross-OS report.

Full samples, commands and hashes: [range-kernels-smoke-2026-10-13.json](range-kernels-smoke-2026-10-13.json).
