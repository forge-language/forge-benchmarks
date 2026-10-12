# Frozen Forge optimization comparison

Proof-gated view index bounds-check elimination versus frozen compiler

Measured `2026-10-12T10:32:03Z` to `2026-10-12T10:33:42Z` with 42 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| lcg | baseline | rust | 1.0047 [1.0043, 1.0051] | 1.0000 [1.0000, 1.0000] | below target |
| lcg | candidate | rust | 1.0046 [1.0038, 1.0051] | 0.9998 [0.9996, 1.0001] | below target |
| primes | baseline | rust | 1.0111 [1.0106, 1.0115] | 1.0000 [1.0000, 1.0000] | below target |
| primes | candidate | rust | 1.0116 [1.0111, 1.0118] | 1.0003 [0.9999, 1.0009] | below target |
| scan | baseline | rust | 1.9600 [1.9513, 1.9640] | 1.0000 [1.0000, 1.0000] | supported for this case |
| scan | candidate | rust | 2.2552 [2.2461, 2.2613] | 1.1488 [1.1441, 1.1540] | supported for this case |
| builder | baseline | rust | 1.2811 [1.2437, 1.2907] | 1.0000 [1.0000, 1.0000] | supported for this case |
| builder | candidate | rust | 1.2817 [1.2691, 1.2876] | 1.0019 [0.9949, 1.0067] | supported for this case |
| immutable | baseline | rust | 18.2461 [18.1519, 18.4228] | 1.0000 [1.0000, 1.0000] | supported for this case |
| immutable | candidate | rust | 19.4459 [19.2381, 19.6484] | 1.0683 [1.0637, 1.0748] | supported for this case |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

The measurement window overlapped a long-running OMO review process that was active across the allowed CPUs; it used about 21% CPU when checked shortly after the run. Paired scheduling reduces but does not eliminate this shared-host interference. Treat the observed gains as promising evidence and confirm them in a quiet-host rerun before relying on their exact magnitude.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. Every implementation must match the independent reference for prewarm and measured inputs. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Rust builder retains its final clone to match the Forge immutable snapshot. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [forge-view-bounds-full-20261012.json](forge-view-bounds-full-20261012.json).
