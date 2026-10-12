# Immutable append lowering: paired compiler comparison

The same Forge/Rust fixture and timer were built with the compiler immediately before the private append-loop lowering and the current compiler. Both builds use the same current runtime archive, stdlib archive, public headers, C flags, Rust compiler, and CPU affinity. The fixture excludes `immutable_view` and uses the older `str_builder()` / `str_builder_finish()` pattern API so the baseline compiler can compile it; the Rust source and clock are identical. The measured immutable loop itself is unchanged.

Measured `2026-10-12T09:19:41Z` to `2026-10-12T09:21:58Z`, 42 position-balanced pairs per workload. All 99 correctness checks, 630 prewarms, and 630 measured checksums matched the independent oracle.

| Workload | Baseline Forge/Rust (95% interval) | Current Forge/Rust (95% interval) | Current/baseline Forge (95% interval) | 1.10 vs Rust |
| --- | ---: | ---: | ---: | --- |
| lcg | 1.0009 [0.9980, 1.0050] | 1.0036 [1.0000, 1.0075] | 1.0013 [0.9993, 1.0057] | below target |
| primes | 1.0102 [1.0076, 1.0127] | 1.0102 [1.0082, 1.0127] | 1.0017 [0.9996, 1.0045] | below target |
| scan | 1.9434 [1.9103, 1.9578] | 1.9490 [1.9176, 1.9631] | 1.0019 [0.9987, 1.0137] | supported for this case |
| builder | 1.1983 [1.0014, 1.2675] | 1.2084 [1.0931, 1.2740] | 1.0132 [0.9820, 1.0959] | inconclusive |
| immutable | 0.2319 [0.2309, 0.2342] | 18.0431 [17.2501, 18.3175] | 77.5045 [74.4483, 78.6935] | supported for this case |

Baseline compiler source: `88290b8 Record follow-up performance evidence`; current compiler source: `4bdd4ec Transfer private builder buffers in optimized loops`.
Both variants use Rust binary SHA-256 `3d75ca05ff0f64d91c3988325bc4b37edd01239a6d5f443766243fce7c5c2f22` and identical fixture hashes for Forge source, Rust source, and clock. Compiler binary hashes differ; runtime, stdlib, and header hashes match.

The current compiler’s generated C contains `fr_str_builder_finish_take` after the proven private loop; the baseline generated C retains repeated `fr_str_append` calls. The immutable workload improved from 0.232x to 18.043x Rust, and from 402.397 ms to 5.235 ms median in this run. This demonstrates the lowering for this specific workload and host. It does not establish language-wide 110% performance. The `builder` row has a current Forge/Rust point estimate above 1.10, but its interval overlaps the threshold; it remains inconclusive.

All samples, hashes, commands, and checks are in the raw JSON. Bootstrap confidence intervals are per row for this run; no outlier samples were excluded.

[Raw provenance and samples](compiler-append-lowering-2026-10-12.json).
