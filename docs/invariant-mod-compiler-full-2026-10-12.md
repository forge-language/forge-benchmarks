# Frozen Forge optimization comparison

Compiler-only invariant-parameter remainder lowering; stable integer parameters used as divisors in loops get exact reciprocal descriptors. Parameter assignments, shadowing, move/receive/yield/await paths, exhausted scan budgets and unknown operand types fail closed. Negative dividends, divisors <=1 and targets without int128 retain checked signed remainder. SDK archives and headers, Forge/Rust fixtures and timer are identical. Both language fixtures use the 3/5 small-prime prefilter. This compares compiler versions, not asymmetric prime algorithms.

Measured `2026-10-12T23:52:35Z` to `2026-10-12T23:54:38Z` with 60 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| lcg | baseline | rust | 1.5058 [1.5043, 1.5089] | 1.0000 [1.0000, 1.0000] | supported for this case |
| lcg | invariant_mod | rust | 1.5039 [1.5013, 1.5077] | 1.0009 [0.9987, 1.0030] | supported for this case |
| primes | baseline | rust | 1.0255 [1.0182, 1.0361] | 1.0000 [1.0000, 1.0000] | below target |
| primes | invariant_mod | rust | 1.5503 [1.4905, 1.5826] | 1.4945 [1.4728, 1.5344] | supported for this case |
| scan | baseline | rust | 1.9405 [1.9053, 1.9578] | 1.0000 [1.0000, 1.0000] | supported for this case |
| scan | invariant_mod | rust | 2.2430 [2.2129, 2.2579] | 1.1590 [1.1474, 1.1681] | supported for this case |
| builder | baseline | rust | 0.9871 [0.9499, 1.1210] | 1.0000 [1.0000, 1.0000] | inconclusive |
| builder | invariant_mod | rust | 1.0679 [1.0185, 1.1568] | 1.0468 [0.9874, 1.0899] | inconclusive |
| immutable | baseline | rust | 18.8804 [16.8583, 19.6768] | 1.0000 [1.0000, 1.0000] | supported for this case |
| immutable | invariant_mod | rust | 13.5618 [11.6292, 17.2869] | 0.9586 [0.8221, 1.0203] | supported for this case |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. Every implementation must match the independent reference for prewarm and measured inputs. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. These fixtures use Forge str_builder_finish_take and Rust String ownership transfer; neither copies the finished builder buffer. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [invariant-mod-compiler-full-2026-10-12.json](invariant-mod-compiler-full-2026-10-12.json).
