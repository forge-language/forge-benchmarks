# Frozen Forge optimization comparison

Standard SDK archives versus the same C runtime/stdlib sources built with LTO

Measured `2026-10-12T09:34:45Z` to `2026-10-12T09:35:48Z` with 42 position-balanced pairs per workload. One preserved Rust binary is shared by every variant.

| Workload | Variant | Rust control | Forge/Rust throughput (95% interval) | Baseline speedup (95% interval) | 1.10 threshold |
| --- | --- | --- | ---: | ---: | --- |
| scan | baseline | rust | 1.9538 [1.9296, 1.9663] | 1.0000 [1.0000, 1.0000] | supported for this case |
| scan | lto | rust | 1.9352 [1.8847, 1.9411] | 0.9926 [0.9862, 1.0006] | supported for this case |
| builder | baseline | rust | 0.9917 [0.9453, 1.0904] | 1.0000 [1.0000, 1.0000] | below target |
| builder | lto | rust | 0.9947 [0.9168, 1.1288] | 0.9795 [0.9215, 1.0307] | inconclusive |
| immutable | baseline | rust | 18.0463 [12.0643, 18.2441] | 1.0000 [1.0000, 1.0000] | supported for this case |
| immutable | lto | rust | 12.1078 [10.4313, 15.5703] | 1.0029 [0.9564, 1.1413] | supported for this case |

All small-input, prewarm and measured outputs match the independent Python reference. All samples remain in the raw report. Confidence is per row and describes this host/run, not simultaneous or universal confidence. Cyclic schedules balance ordinal positions but not every adjacency.

Compiler/runtime/stdlib changes are identified by exact binary, archive, header and generated-C hashes. Every implementation must match the independent reference for prewarm and measured inputs. FG/Rust workload and common timer sources are identical across variants. Raw source-state observations can differ from frozen SDK content; artifact hashes identify the actual build inputs.

Both implementations complete the same runtime-input algorithms and final checksums. Forge retains immutable arena snapshots until reset; Rust can drop obsolete owned strings sooner. Rust builder retains its final clone to match the Forge immutable snapshot. Allocator lifetime, out-of-line SDK calls, compiler range analysis and runtime policies are real implementation differences. No measured algorithm is delegated to C FFI.

These five CPU/string cases do not establish full language, HTTP, coroutine, mailbox, vector, ownership or other-machine performance. See the separate arithmetic distribution probe for possible cost of narrowing guards on wide/negative inputs.

Raw provenance and all samples: [sdk-lto.json](sdk-lto.json).

LTO did not produce a supported gain over the normal SDK in these paired results: the LTO/normal Forge throughput ratio was 0.993x for scan [0.986–1.001], 0.979x for builder [0.921–1.031], and 1.003x for immutable append [0.956–1.141]. The standard archive remains preferable as the default; this run does not justify changing the SDK build policy. The LTO SDK passed all 10 stdlib CTest cases.
