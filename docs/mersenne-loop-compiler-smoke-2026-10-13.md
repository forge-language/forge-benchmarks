# Native cross-OS CPU comparison

Platform: `Linux-6.8.0-139-generic-x86_64-with-glibc2.39` / `x86_64`. Measured 12 balanced triples per workload, seed 20261013.

| Workload | Candidate / baseline (95% interval) | Candidate / Rust (95% interval) | Rust 1.10 |
| --- | ---: | ---: | --- |
| lcg | 0.9733 [0.8837, 1.0207] | 1.2195 [1.1643, 1.5071] | supported for this case |

All measured checksums and same-input warmups match an independent Python reference. All six three-way permutations occur equally often. Each row has a paired-ratio bootstrap 95% interval; this is not simultaneous confidence over workloads or proof for all programs.

Both Forge versions share identical SDK archives/headers, source algorithms and clock; one Rust control is used throughout. C uses -O3/native CPU tuning/LTO; Rust uses opt-level=3, target-cpu=native, thin LTO and disabled overflow checks. Process startup is excluded from kernel times. All platforms use unpinned child processes; virtualized/shared runners and frequency changes remain sources of noise. Compare before/after ratios within each OS; absolute times across different OS/hardware/architectures are not OS-only causal comparisons.

Builder transfers the buffer in both implementations. Immutable append uses different allocation/lifetime policies. CPU results do not prove HTTP capacity, memory-safety equivalence or universal language throughput. Build failures are recorded as failed_no_claim and must not be silently removed from the cross-OS report.

Full samples, commands and hashes: [mersenne-loop-compiler-smoke-2026-10-13.json](mersenne-loop-compiler-smoke-2026-10-13.json).
