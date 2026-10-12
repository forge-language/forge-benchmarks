# Function-level prime range versioning probe — rejected

This experiment tested whether the prime loop could amortize a range check over
an entire `primes(n, rounds, seed)` call. The temporary generated-C candidate
checked once that every loop value lies in `[0, UINT32_MAX]`. It then ran a
duplicated loop with unsigned 32-bit values and trial divisors, using the
original 64-bit implementation for every input outside that range. Forge
source, Rust source, runtime, standard library and benchmark dimensions stayed
unchanged; only the generated C and Forge executable differed. This was a
prototype of whole-function loop versioning, not a compiler change.

The guard proved the fast-path preconditions for positive `n` and `rounds`:
both loop bounds fit `uint32_t`; `seed + 1,000,001` is nonnegative and fits
`uint32_t`; and the full iteration count fits below the remaining `uint32_t`
value range. Therefore each value and divisor is identical on the fast path,
the 32-bit divisor loop stops before overflow, and the wrapping sum is retained
through `uint64_t` accumulation followed by Forge's bit-preserving conversion.
All inputs failing the guard use the unchanged 64-bit implementation.

Fourteen direct inputs matched a separate reference, including values at and
around the fast-path boundary, negative seeds, `INT64_MIN`, `INT64_MAX`, empty
loops, and the measured dimensions. The preserved paired harness then checked
15 correctness cases, 360 prewarms and 360 measurements against its independent
reference. It ran 120 position-balanced pairs on CPU 0 for `n=2000`,
`rounds=128`, comparing baseline Forge, the function-versioned Forge binary,
and one shared Rust binary.

| Variant | Forge median | Rust median | Rust / Forge throughput (95% interval) | Candidate / baseline Forge throughput (95% interval) |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 74.598 ms | 75.456 ms | 1.0103 [1.0096, 1.0116] | 1.0000 |
| Function-versioned | 75.284 ms | 75.456 ms | 1.0003 [0.9989, 1.0025] | 0.9905 [0.9881, 0.9914] |

The candidate was about 1% slower than baseline Forge and did not approach the
1.10 Rust-throughput target. Disassembly confirms that the candidate emitted
32-bit unsigned divides in its fast loop, while retaining the 64-bit signed
fallback; the width change and one-time guard were insufficient to compensate
for cloning and selecting the loop. This versioning design is rejected.

The complete sample set, input checks, build metadata, fixture hashes and
command provenance are in [the raw comparison](prime-function-versioned-2026-10-12.json)
and [the generated summary](prime-function-versioned-2026-10-12-generated.md).
An independent OMO `explore` review confirmed the fast-path range proof,
intermediate-width safety, result counts and reported medians/intervals.
