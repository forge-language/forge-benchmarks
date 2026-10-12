# Positive constant remainder lowering

The compiler now has a candidate path that emits native C `%` for a positive
integer literal divisor when the left expression is known to have integer or
boolean type. Positive divisors cannot trigger Forge's zero-divisor or
`INT64_MIN / -1` remainder trap. The left expression and literal are each
emitted once. Dynamic, zero, negative and unknown-type cases retain the checked
helper. This removes the checked helper branch while allowing the C compiler to
lower constant remainders directly.

The new arithmetic regression covers `INT64_MIN`, adjacent and signed edge
values through a function parameter at both native `-O0` and `-O3`. The full
21-suite CTest run passed, including arithmetic, self-hosting, JS and compiler
regressions. The benchmark runner passed 99 correctness checks and all 720
prewarm and 720 measured checksums across the five CPU/string workloads.

Baseline, candidate and one shared Rust control ran in a 48-pair
position-balanced schedule for each workload. The compiler change did not alter
Forge/Rust fixture sources, runtime, stdlib, headers or timer. The standout
result was scan: Forge/Rust rose from 1.9285 [1.9039, 1.9551] to 2.2504
[2.2330, 2.2738], and the paired Forge candidate speedup was 1.1571
[1.1509, 1.1729]. This clears the 1.10 target for this scan workload on this
host/run.

| Workload | Candidate Forge/Rust | Candidate vs baseline Forge | Result |
| --- | ---: | ---: | --- |
| LCG | 1.0018 [0.9991, 1.0066] | 0.9997 [0.9951, 1.0032] | unchanged; below 1.10 |
| Primes | 1.0088 [1.0062, 1.0138] | 0.9989 [0.9966, 1.0014] | unchanged; below 1.10 |
| Scan | 2.2504 [2.2330, 2.2738] | 1.1571 [1.1509, 1.1729] | 15.7% faster; above 1.10 |
| Builder | 1.0827 [1.0118, 1.2413] | 1.0734 [0.9626, 1.1141] | inconclusive |
| Immutable append | 12.2314 [10.3983, 18.7297] | 0.9839 [0.9077, 1.0594] | no supported change; above 1.10 |

This is a targeted codegen optimization, not evidence that all Forge programs
reach 110% of Rust. LCG and prime search still need work. [Full method, hashes
and raw paired samples](positive-constant-remainder-lowering-2026-10-12.json).
