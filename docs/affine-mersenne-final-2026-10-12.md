# Arithmetic compiler comparison

Compiler diagnostic microbenchmark. Ratios are elapsed baseline / candidate and Rust / candidate for identical work. A value above 1 means faster candidate throughput.

| Distribution | Baseline ms | Candidate ms | Rust ms | Baseline/candidate median [95% CI] | Rust/candidate median [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: |
| affine_lcg | 32.592 | 18.279 | 38.308 | 1.7861 [1.7614, 1.7925] | 2.1024 [2.0864, 2.1119] |

8000000 iterations per sample, 60 measured groups. Protocol: three-way prewarmed balanced all permutations. Every timed sample follows a same-input prewarm and matches the independent Python oracle. All raw samples, warmups, arguments, hashes and compiler commands are retained in the JSON report.

The affine_lcg workload applies value = (value * 48271 + 1) % 2147483647 for each iteration from a positive runtime seed. The candidate compiler lowers this source expression through a guarded Mersenne multiply-add fold, with the exact wrapping multiply-add and signed remainder as the fallback. Rust uses explicit wrapping multiplication and addition. The independent oracle exponentiates the affine map modulo 2^31-1, avoiding a second iterative implementation.

Both Forge compilers link exactly the same frozen native archives and headers. GCC -O3, native tuning and LTO are matched by Rust opt-level=3, native tuning, thin LTO and one codegen unit; Rust updates explicitly wrap to match Forge. Input/output barriers occur outside the loop. Parser, startup and output time are excluded from kernel timing. RSS is whole-process wait4 information, including possible pre-exec runner footprint; it is not a precise language heap measurement.

Shared-host scheduling/frequency noise remains despite affinity and balanced order. Bootstrap intervals are per-row median estimates from this run and are not family-wise confidence or a universal 110% guarantee. No result is discarded or retried after a checksum failure.
