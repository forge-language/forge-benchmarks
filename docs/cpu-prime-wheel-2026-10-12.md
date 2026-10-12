# Prime-loop wheel-factorization experiment

The candidate tests divisibility by 2 and 3 once, then tests both `6k-1` and
`6k+1` divisors. It returns the same prime sum as trial division. Forge and Rust
used source-matched candidate implementations, identical compiler/SDK archives,
headers, timer, dimensions, and balanced execution. The original fixture and
Python oracle had edge-case errors for values below 2 and for primes 2 and 3;
commit `9c7e27c` fixes those cases. Both experimental variants included that
correction before measurement.

| Comparison | Forge median | Rust median | Forge/Rust throughput (95% interval) |
| --- | ---: | ---: | ---: |
| Corrected trial-division baseline | 74.600 ms | 75.239 ms | 1.0126 [1.0078, 1.0164] |
| Wheel candidate, matched Rust control | 50.085 ms | 50.322 ms | 1.0074 [1.0025, 1.0103] |

The candidate reduced both implementations' median time by about 1.49x versus
the corrected baseline (95% paired interval 1.4808–1.4964). This is an
algorithm-level speedup shared by Forge and Rust; its source-matched Forge/Rust
ratio stays near 1.0 and does not approach the 1.10 target. The candidate is
therefore not adopted as evidence of a Forge compiler performance gain.

The 24-pair comparison used the established dimensions `n=2000`, `rounds=128`,
CPU 0, same-input prewarm, exact Python sieve oracle, and position-balanced
execution. All correctness, prewarm, and measured checksums passed. The
confidence interval is per row and host-specific. The JSON preserves all
samples, binary/source hashes, build commands, and the matching Rust control.

Reproduction patch: [cpu-prime-wheel-2026-10-12.patch](cpu-prime-wheel-2026-10-12.patch). Full frozen build snapshots:
[cpu-prime-wheel-2026-10-12.raw.tar.gz](cpu-prime-wheel-2026-10-12.raw.tar.gz) (SHA-256 `955a638a26bc9b06b4050e4b56b32ac8deddb0c94d7fb85a61bfa94947358b57`). Machine-readable
report: [cpu-prime-wheel-2026-10-12.json](cpu-prime-wheel-2026-10-12.json).
