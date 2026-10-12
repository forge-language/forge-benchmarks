# Builder length publication order experiment

Measured `2026-10-12T08:26:21Z` to `2026-10-12T08:27:44Z` with 60 paired samples per workload on CPU 0. Baseline and candidate use the same compiler, runtime and stdlib archives, Rust control, benchmark sources, pre-reserved builder, and runtime inputs. The only difference is the inline builder-char fast path: baseline uses `data[len++] = byte`; candidate writes `data[len] = byte` and then publishes `len + 1`.

| Workload | Baseline / Rust | Candidate / Rust | Candidate / baseline (95% interval) |
| --- | ---: | ---: | ---: |
| scan | 0.944x [0.940, 0.948] | 0.942x [0.937, 0.947] | 0.996x [0.992, 1.006] |
| builder | 0.969x [0.921, 0.985] | 0.870x [0.832, 0.931] | 0.964x [0.915, 1.000] |

The length-store ordering did not improve either workload. The builder result points to a possible regression, although its paired interval narrowly reaches 1.0. The candidate was discarded. All checksums matched the independent reference for all measured inputs. The confidence intervals describe this host and run and are not a language-wide performance claim.

The full raw report preserves per-sample timings, seeds, commands, source state and artifact hashes: [builder-length-publication-2026-10-12.json](builder-length-publication-2026-10-12.json).
