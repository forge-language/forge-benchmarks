# Builder capacity invariant candidate

Same-session measurement from `2026-10-12T23:38:38Z` to `2026-10-12T23:40:40Z`. Each workload has 60 randomized, order-balanced triples of baseline, candidate and Rust, with checked same-input prewarming. Compiler/runtime and workload/timer source hashes are identical. Both snapshots use matched Forge/Rust small-prime prefilters. The baseline checks cap > len before checking cap - len > 1; the candidate relies on the API-created builder invariant len <= cap and checks cap - len > 1 directly. Byte validation, growth and finish APIs are unchanged.

| Workload | Baseline / Rust | Candidate / Rust (95% interval) | Candidate speedup (95% interval) | 1.10 target |
| --- | ---: | --- | --- | --- |
| lcg | 1.5049 | 1.5034 [1.4998, 1.5092] | 0.9992 [0.9961, 1.0017] | supported for this case |
| primes | 1.0314 | 1.0264 [1.0152, 1.0393] | 0.9986 [0.9910, 1.0157] | below target |
| scan | 1.9384 | 1.9175 [1.8891, 1.9294] | 0.9939 [0.9833, 0.9997] | supported for this case |
| builder | 0.9883 | 0.9526 [0.9227, 1.0397] | 1.0052 [0.9322, 1.0562] | below target |
| immutable | 18.5695 | 19.2494 [16.4377, 20.1794] | 1.0538 [1.0037, 1.1142] | supported for this case |

The native stdlib archive is also byte-for-byte identical between these snapshots. This experiment isolates changes in the checked installed header when compiling callers; it reuses the preserved compiler/runtime rather than attributing concurrent compiler/runtime changes to this optimization.

Every correctness, prewarm and measured checksum matches an independent Python reference. All samples remain in the raw report. Confidence intervals describe these paired ratios on this host and are not simultaneous confidence over all workloads. The original and earlier different-date view-inline reports remain preserved separately.

The fast path preserves exported builder-char symbols and the existing data/length/capacity layout. Invalid bytes and null handles fail, capacity subtraction avoids overflow, and growth delegates to the external ABI. Views/builders still require trusted live arena handles; this is not a general memory-safety guarantee. Snapshot contracts are those of the recorded fixtures and source APIs; copying finish and ownership-transfer finish both preserve independence from subsequent builder mutation. Rust and Forge retain their documented allocation lifetime differences.

Finite CPU kernels do not establish language-wide 110% throughput, HTTP/application performance, safe vector support, or cross-machine portability. Whole-process RSS is a diagnostic and can include the forked runner before exec.

Raw samples and source/artifact hashes: [builder-capacity-invariant-2026-10-12.json](builder-capacity-invariant-2026-10-12.json).

Decision: rejected. The builder speedup interval includes no change, while scan regressed slightly in this run. The original checked header has been restored. Both the native and ABI string test variants, all 11 stdlib CTests, and the optimized UBSan-instrumented string caller test passed with the candidate. [Exact candidate patch](builder-capacity-invariant-2026-10-12.patch).

The original Forge binary is byte-identical to the previously measured
small-prime candidate. Matching the Rust 3/5 prefilter reduces its prime ratio
to 1.0314 [1.0177, 1.0436], below 1.10. Thus the previous ~1.69 comparison
included algorithm asymmetry. The baseline builder ratio is also below 1.10
in this run (0.9883 [0.9266, 1.0599]); previous single-run builder support
cannot establish stable 1.10 performance. The source of timing variability
has not been isolated.

Frozen compiler/SDK/source inputs and both executables are in
[the raw archive](builder-capacity-invariant-2026-10-12.raw.tar.gz), SHA-256
`83067692b91a1bc7eef1b7cc57b414a295913a98e0246b5de7f15966b049091c`.
