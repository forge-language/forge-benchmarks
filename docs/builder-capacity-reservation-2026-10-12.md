# Capacity-aware string builder comparison

A 120-pair position-balanced comparison isolates Forge builder capacity reservation. The baseline calls `str_builder()` and the candidate calls `str_builder_with_capacity(n)`; the compiler, runtime, stdlib, headers, clock, dimensions, and Rust fixture are held fixed. Rust already constructs the matching `String` with `String::with_capacity(n)`. All correctness and timed results match the independent reference.

Measured `2026-10-12T09:29:29Z` to `2026-10-12T09:31:16Z`. The runner checked 28 edge cases, 480 prewarm inputs and 480 timed inputs.

| Implementation | Forge/Rust throughput (95% interval) | Median time |
| --- | ---: | ---: |
| baseline vs shared Rust | 1.0321 [0.9546, 1.1357] | 92.242 ms |
| capacity vs shared Rust | 1.0929 [1.0158, 1.1999] | 86.891 ms |

Capacity reservation improved Forge throughput by 1.0246x over the default-capacity builder, 95% interval [1.0066, 1.0679]. The source-matched Rust control shows 1.0929x Forge/Rust for the candidate; the alternative matching Rust binary reports 1.0996x. Both intervals cross the 1.10 threshold, so this does not establish Forge at 110% of Rust.

This is one host and one builder workload. It supports a modest local benefit from preallocation, not a general language performance claim.

[Raw provenance and all samples](builder-capacity-reservation-2026-10-12.json).
