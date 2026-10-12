# Frozen Forge optimization comparison

Checked builder snapshot-copy API compared against both the preserved Rust clone control and an idiomatic Rust move control. Move returns identical bytes/checksum and consumes the builder; it omits the independent snapshot-copy operation, so the two Rust ownership contracts are reported separately.

Measured `2026-10-12T00:20:32Z` to `2026-10-12T00:20:50Z` with 20 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| builder | baseline | rust | 0.9056 [0.9023, 0.9082] | 1.0000 [1.0000, 1.0000] | below target |
| builder | baseline | rust_move | 0.9021 [0.8943, 0.9040] | 1.0000 [1.0000, 1.0000] | below target |
| builder | strings | rust | 1.0006 [0.9909, 1.0063] | 1.1087 [1.0476, 1.1122] | below target |
| builder | strings | rust_move | 0.9986 [0.9814, 1.0029] | 1.1087 [1.0476, 1.1122] | below target |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Rust builder retains its final clone to match the Forge immutable snapshot. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [builder-copy-move-controls-2026-10-12.json](builder-copy-move-controls-2026-10-12.json).
