# Forge event-loop burst drain benchmark

One burst of simultaneously-ready eventfds drained through Forge callbacks and direct Rust epoll_wait.

48 paired samples per event count, pinned to CPU 0. Rust uses batch capacity 1024.

| Ready eventfds | Implementation | Median drain (us) | Poll calls | Forge/Rust throughput | Candidate/base speedup |
| ---: | --- | ---: | ---: | ---: | ---: |
| 64 | base | 7.47 | 1.0 | 1.0132x | 1.0000x |
| 64 | candidate | 7.47 | 1.0 | 1.0001x | 0.9922x |
| 64 | rust | 7.50 | 1.0 | 1.0000x | 1.0000x |
| 256 | base | 28.82 | 4.0 | 0.9644x | 1.0000x |
| 256 | candidate | 27.61 | 1.0 | 1.0089x | 1.0415x |
| 256 | rust | 27.87 | 1.0 | 1.0000x | 1.0000x |
| 1024 | base | 117.50 | 16.0 | 0.9487x | 1.0000x |
| 1024 | candidate | 113.72 | 4.0 | 0.9802x | 1.0287x |
| 1024 | rust | 112.25 | 1.0 | 1.0000x | 1.0000x |
| 4096 | base | 774.95 | 64.0 | 0.9769x | 1.0000x |
| 4096 | candidate | 696.72 | 16.0 | 1.0587x | 1.0519x |
| 4096 | rust | 764.45 | 4.0 | 1.0000x | 1.0000x |

All event IDs were observed once before the timer stopped; setup/signaling are excluded from the timed drain. Confidence intervals are paired and per row.
This event-loop microbenchmark measures burst-drain behavior, not application or scheduler throughput. Forge dispatches through the public C callback API; Rust calls epoll_wait directly, a strict lower-level control.

All samples and provenance: [event-batch-256-final-48-2026-10-12.json](event-batch-256-final-48-2026-10-12.json).
