# Frozen Forge optimization comparison

Recheck the isolated stage-0 codegen loop-increment proof after the OMO read-only audit finished; baseline is immediately preceding compiler commit. Identical frozen runtime/stdlib archives and CPU/Rust fixture.

Measured `2026-10-12T07:10:06Z` to `2026-10-12T07:11:24Z` with 18 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| lcg | baseline | rust | 1.0057 [0.9986, 1.0101] | 1.0000 [1.0000, 1.0000] | below target |
| lcg | loop_proof | rust | 1.0049 [0.9999, 1.0083] | 0.9980 [0.9961, 1.0053] | below target |
| primes | baseline | rust | 1.0092 [1.0062, 1.0132] | 1.0000 [1.0000, 1.0000] | below target |
| primes | loop_proof | rust | 1.0116 [1.0088, 1.0168] | 1.0043 [0.9991, 1.0070] | below target |
| scan | baseline | rust | 0.9462 [0.9373, 0.9518] | 1.0000 [1.0000, 1.0000] | below target |
| scan | loop_proof | rust | 0.9405 [0.9328, 0.9463] | 0.9978 [0.9816, 1.0034] | below target |
| builder | baseline | rust | 1.0010 [0.8913, 1.0099] | 1.0000 [1.0000, 1.0000] | below target |
| builder | loop_proof | rust | 0.9970 [0.9555, 1.0074] | 0.9963 [0.9559, 1.1072] | below target |
| immutable | baseline | rust | 0.2302 [0.2293, 0.2342] | 1.0000 [1.0000, 1.0000] | below target |
| immutable | loop_proof | rust | 0.2303 [0.2285, 0.2319] | 0.9933 [0.9914, 1.0004] | below target |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Rust builder retains its final clone to match the Forge immutable snapshot. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [compiler-loop-proof-recheck-2026-10-12.json](compiler-loop-proof-recheck-2026-10-12.json).
