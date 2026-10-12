# Forge event-loop burst drain benchmark

One burst of simultaneously-ready eventfds drained through Forge callbacks and direct Rust epoll_wait.

48 paired samples per event count, pinned to CPU 0. Rust uses batch capacity 1024.

| Ready eventfds | Implementation | Median drain (us) | Poll calls | Forge/Rust throughput | Candidate/base speedup |
| ---: | --- | ---: | ---: | ---: | ---: |
| 64 | base | 7.45 | 1.0 | 1.0052x | 1.0000x |
| 64 | candidate | 7.46 | 1.0 | 1.0005x | 0.9964x |
| 64 | rust | 7.45 | 1.0 | 1.0000x | 1.0000x |
| 256 | base | 28.86 | 4.0 | 0.9536x | 1.0000x |
| 256 | candidate | 27.83 | 1.0 | 0.9933x | 1.0393x |
| 256 | rust | 27.48 | 1.0 | 1.0000x | 1.0000x |
| 1024 | base | 118.16 | 16.0 | 0.9538x | 1.0000x |
| 1024 | candidate | 114.51 | 4.0 | 0.9876x | 1.0378x |
| 1024 | rust | 113.58 | 1.0 | 1.0000x | 1.0000x |
| 4096 | base | 778.23 | 64.0 | 0.9352x | 1.0000x |
| 4096 | candidate | 698.40 | 16.0 | 1.0125x | 1.0413x |
| 4096 | rust | 774.91 | 4.0 | 1.0000x | 1.0000x |

All event IDs were observed once before the timer stopped; setup/signaling are excluded from the timed drain. Confidence intervals are paired and per row.
This event-loop microbenchmark measures burst-drain behavior, not application or scheduler throughput. Forge dispatches through the public C callback API; Rust calls epoll_wait directly, a strict lower-level control.

Rust-relative candidate results (median paired throughput and 95% interval):

- 64 ready descriptors: Forge/Rust 1.0005x [0.9937, 1.0063], candidate/base 0.9964x [0.9892, 1.0081], 1.10 status: below target.
- 256 ready descriptors: Forge/Rust 0.9933x [0.9842, 1.0009], candidate/base 1.0393x [1.0308, 1.0506], 1.10 status: below target.
- 1024 ready descriptors: Forge/Rust 0.9876x [0.9721, 1.0052], candidate/base 1.0378x [1.0276, 1.0452], 1.10 status: below target.
- 4096 ready descriptors: Forge/Rust 1.0125x [0.9755, 1.0967], candidate/base 1.0413x [0.9591, 1.0975], 1.10 status: below target.

All samples and provenance: [event-batch-256-adopted-48-2026-10-12.json](event-batch-256-adopted-48-2026-10-12.json).

Decision: keep capacity 256. It preserves the 64-ready-fd case, reduces polling from four calls to one at 256 ready descriptors, and improves measured drain throughput by about 4% at 256 and 1024 ready descriptors. The 4096 result is noisy and does not establish a 10% gain over Rust. Capacity 1024 was rejected because it materially regressed the 64- and 256-ready-fd cases; see [the comparison](event-batch-1024-48-2026-10-12.md). The selected runtime change is commit `0b1e7d4` in forge-runtime.
