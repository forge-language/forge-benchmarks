# Native cross-OS CPU comparison

Platform: `Linux-6.8.0-139-generic-x86_64-with-glibc2.39` / `x86_64`. Measured 12 balanced triples per workload, seed 20261013.
**Generated-C experiment `reserved-builder`: the candidate C helper is modified after emission. These results do not measure the shipped compiler unchanged.**


| Workload | Candidate / baseline (95% interval) | Candidate / Rust (95% interval) | Rust 1.10 |
| --- | ---: | ---: | --- |
| lcg | 0.9981 [0.9403, 1.1798] | 1.2538 [1.1659, 1.5056] | supported for this case |
| primes | 1.5200 [1.3864, 1.6926] | 1.4380 [0.8094, 1.6451] | inconclusive |
| scan | 1.1112 [1.0058, 1.1579] | 1.6204 [1.4837, 1.7299] | supported for this case |
| builder | 1.3483 [1.2767, 1.6565] | 1.4205 [1.3061, 1.6692] | supported for this case |
| immutable | 0.9880 [0.9304, 1.3915] | 7.9852 [6.2101, 16.0462] | supported for this case |

All measured checksums and same-input warmups match an independent Python reference. All six three-way permutations occur equally often. Each row has a paired-ratio bootstrap 95% interval; this is not simultaneous confidence over workloads or proof for all programs.

Both Forge versions share identical SDK archives/headers, source algorithms and clock; one Rust control is used throughout. C uses -O3/native CPU tuning/LTO; Rust uses opt-level=3, target-cpu=native, thin LTO and disabled overflow checks. Process startup is excluded from kernel times. All platforms use unpinned child processes; virtualized/shared runners and frequency changes remain sources of noise. Compare before/after ratios within each OS; absolute times across different OS/hardware/architectures are not OS-only causal comparisons.

Builder transfers the buffer in both implementations. Immutable append uses different allocation/lifetime policies. CPU results do not prove HTTP capacity, memory-safety equivalence or universal language throughput. Build failures are recorded as failed_no_claim and must not be silently removed from the cross-OS report.

Full samples, commands and hashes: [reserved-builder-smoke-2026-10-13.json](reserved-builder-smoke-2026-10-13.json).
