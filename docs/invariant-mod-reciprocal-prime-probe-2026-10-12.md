# Frozen Forge optimization comparison

Generated-C arithmetic prototype: descriptor prepared once per invariant modulus in prime_mod_pow and prime_mr_pass; positive dividends and divisors >1 use an exact ceil(2^64/divisor) reciprocal, high-half multiply and at most one correction. Other inputs and targets without 128-bit integers use original checked signed remainder. Matched small-prime filters in Forge and Rust; identical Forge/Rust source snapshots and SDK. This does not yet implement a generic compiler lowering.

Measured `2026-10-12T23:46:36Z` to `2026-10-12T23:46:49Z` with 60 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| primes | baseline | rust | 1.0240 [1.0164, 1.0327] | 1.0000 [1.0000, 1.0000] | below target |
| primes | reciprocal | rust | 1.5058 [1.4298, 1.5386] | 1.4788 [1.3935, 1.5050] | supported for this case |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. Every implementation must match the independent reference for prewarm and measured inputs. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. These fixtures use Forge str_builder_finish_take and Rust String ownership transfer; neither copies the finished builder buffer. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [invariant-mod-reciprocal-prime-probe-2026-10-12.json](invariant-mod-reciprocal-prime-probe-2026-10-12.json).
