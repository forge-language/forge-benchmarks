# Integer division trap branch hint experiment

A compiler candidate marked integer division/remainder trap checks as unlikely
using a GNU/Clang branch prediction hint, with a portable no-op fallback. This
kept the checks and failure behavior intact. It was compared against the
immediately preceding compiler commit, `8f999c4`, with one unchanged Rust
control, 24 randomized paired groups per workload, and the same checked CPU
fixtures and dimensions (`LCG 250000 × 64`, `primes 2000 × 128`). Every sample
and prewarm matched the independent reference.

| Workload | Candidate / baseline Forge throughput (95% CI) | Baseline Forge / Rust | Candidate Forge / Rust |
| --- | ---: | ---: | ---: |
| LCG | 0.9956 [0.9909, 0.9994] | 1.0193 | 1.0124 |
| Primes | 0.9866 [0.9815, 0.9887] | 1.0112 | 0.9984 |

The hint regressed both workloads, so the source change was discarded. This
candidate did not move either workload toward the 1.10 Rust-relative target.

[Raw comparison JSON](division-trap-branch-hint-2026-10-12.json), SHA-256
`270f43dde8f9866ae2f361822ded71ce4aff98e76fe374e2fcf4957f0171e541`.
