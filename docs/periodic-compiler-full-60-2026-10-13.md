# Native cross-OS CPU comparison

Platform: `Linux-6.8.0-139-generic-x86_64-with-glibc2.39` / `x86_64`. Measured 60 balanced triples per workload, seed 20261013.

| Workload | Candidate / baseline (95% interval) | Candidate / Rust (95% interval) | Rust 1.10 |
| --- | ---: | ---: | --- |
| lcg | 1.0267 [0.9906, 1.0548] | 1.2697 [1.2420, 1.3407] | supported for this case |
| primes | 1.4177 [1.3032, 1.5488] | 1.4033 [1.3109, 1.5475] | supported for this case |
| scan | 1.7400 [1.6695, 1.8666] | 2.6677 [2.5339, 2.8319] | supported for this case |
| builder | 1.4165 [1.3302, 1.4675] | 1.6526 [1.6085, 1.7281] | supported for this case |
| immutable | 1.1615 [1.0249, 1.2213] | 8.1081 [7.5718, 9.0713] | supported for this case |

All measured checksums and same-input warmups match an independent Python reference. All six three-way permutations occur equally often. Each row has a paired-ratio bootstrap 95% interval; this is not simultaneous confidence over workloads or proof for all programs.

Both Forge versions share identical SDK archives/headers, source algorithms and clock; one Rust control is used throughout. C uses -O3/native CPU tuning/LTO; Rust uses opt-level=3, target-cpu=native, thin LTO and disabled overflow checks. Process startup is excluded from kernel times. All platforms use unpinned child processes; virtualized/shared runners and frequency changes remain sources of noise. Compare before/after ratios within each OS; absolute times across different OS/hardware/architectures are not OS-only causal comparisons.

Builder transfers the buffer in both implementations. Immutable append uses different allocation/lifetime policies. CPU results do not prove HTTP capacity, memory-safety equivalence or universal language throughput. Build failures are recorded as failed_no_claim and must not be silently removed from the cross-OS report.

Full samples, commands and hashes: [periodic-compiler-full-60-2026-10-13.json](periodic-compiler-full-60-2026-10-13.json).
