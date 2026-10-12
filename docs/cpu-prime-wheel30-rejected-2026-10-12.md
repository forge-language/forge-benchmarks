# Rejected matched 30-wheel prime fixture

A source-level Forge/Rust comparison used matched 30-wheel trial-division
fixtures at n=2000, rounds=128. Across 60 paired measurements, Rust/Forge
throughput was 1.0020 with a bootstrap 95% interval [1.0011, 1.0039]. Six
correctness checks, 126 warmups and 120 measured executions passed. This
result is near parity and below the 1.10 target, so the wheel rewrite is not
adopted as a performance win. It remains a reproducible rejected experiment.

The JSON report records fixture hashes, exact build inputs, environment and
all samples: [matched wheel report](cpu-prime-wheel30-matched-2026-10-12.json).
