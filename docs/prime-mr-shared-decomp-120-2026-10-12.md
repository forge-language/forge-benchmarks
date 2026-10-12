# Shared Miller–Rabin decomposition probe — rejected

The bounded Miller–Rabin candidate tests bases 2 and 3 below 1,373,653. Each `prime_mr_pass` previously decomposed the same `value - 1` into `d × 2^s`. This probe moved that decomposition into `prime_is` and passed the identical `(d, s)` to both base tests. The change was applied to matched Forge and Rust fixtures; all other source, compiler/runtime/stdlib archives, benchmark dimensions, and checks remained fixed.

The comparison used 120 balanced six-order paired groups at `n=2000`, `rounds=128`, with a same-seed prewarm before each measurement. All 175 boundary/reference cases, 480 prewarms, and 480 timed results passed the independent sieve checksum. Both candidate binaries matched the baseline Miller–Rabin implementations on the full benchmark and small, negative, cutoff, and larger-value cases.

| Metric | Result (paired median, 95% interval) |
| --- | ---: |
| Candidate Forge throughput / base Miller–Rabin Forge | 1.0021 [0.9993, 1.0042] |
| Base Rust / candidate Forge throughput | 1.0236 [1.0209, 1.0270] |
| Candidate Forge / candidate Rust throughput | 1.0173 [1.0136, 1.0230] |
| Candidate Rust throughput / base Miller–Rabin Rust | 1.0052 [1.0017, 1.0079] |

Sharing `(d, s)` did not produce a measurable Forge improvement over the existing Miller–Rabin Forge implementation. The candidate Forge interval includes parity, while the Rust candidate improved by about 0.5%; the source-matched Forge/Rust result remains well below 1.10. This is a rejected algorithm-level probe, not a compiler performance claim. The shared decomposition requires the second base only when the first base passes, so the possible work reduction is naturally limited to that subset.

The [Forge fixture](../benchmark/cpu/kernels_prime_miller_rabin_shared_decomp.fg), [Rust fixture](../benchmark/cpu/kernels_prime_miller_rabin_shared_decomp.rs), and [full paired samples](prime-mr-shared-decomp-120-2026-10-12.json) preserve exact inputs, hashes, correctness checks, and runner source. The report runner's ratio direction is numerator kernel time divided by denominator kernel time; throughput ratios above are written in the intuitive faster/lower-time direction.
