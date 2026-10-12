# Mersenne constant remainder lowering — rejected

A compiler candidate recognized positive integer divisors of the form
`2^k - 1` for `16 <= k <= 62` and replaced C's constant remainder with four
unsigned folds, a conditional subtraction and sign restoration. The unsigned
absolute-value transformation avoids negating `INT64_MIN` as a signed value.
All other divisors used the already-tested direct constant remainder or the
checked helper.

The fold formula matched truncating signed remainder for 47,470 generated
boundary and random inputs over every shift from 16 through 62. The arithmetic
regression suite passed with the `INT64_MIN` and `INT64_MAX` cases. In the
benchmark runner, all 36 correctness checks and 288 warmup plus 288 measured
checksums matched the independent reference.

The baseline is the positive-constant remainder compiler at `368b9c8`; the
candidate and one shared Rust control were interleaved in 48 position-balanced
pairs for LCG and prime search, with identical fixtures, timer, runtime,
stdlib and headers.

| Workload | Baseline Forge/Rust | Candidate Forge/Rust | Candidate Forge speed vs baseline |
| --- | ---: | ---: | ---: |
| LCG | 1.0045 [0.9976, 1.0088] | 0.6418 [0.6387, 0.6424] | 0.6384 [0.6369, 0.6397] |
| Primes | 1.0116 [1.0101, 1.0132] | 1.0114 [1.0095, 1.0130] | 0.9965 [0.9955, 0.9996] |

The custom fold path made LCG 36% slower than the ordinary C constant
remainder and slightly regressed prime search. The four dependent folds and
sign normalization cost more than the compiler's existing constant-divisor
lowering. The candidate was reverted and is not adopted. [Full paired method,
artifact hashes and raw samples](mersenne-remainder-lowering-2026-10-12.json).
