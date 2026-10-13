# Native current-control periodic scan and arithmetic screening

This is an explicit generated-C experiment; both producers are the same unmodified compiler d4c632b. It is an incremental comparison against the current release, with matched Rust and shared SDK archives/headers per native job. It does not measure a new compiler release. All six jobs in [run 38343347307](https://github.com/forge-language/forge-benchmarks/actions/runs/38343347307) completed, and all 720 direct checks, 5400 same-input prewarms and 5400 measured executions matched independent references.

| Platform / repeat | Workload | Candidate / current Forge (95% interval) | Candidate / Rust (95% interval) |
| --- | --- | ---: | ---: |
| macos-15-0 | lcg | 1.8430 [1.8115,1.8884] | 1.6002 [1.5591,1.6321] |
| macos-15-0 | primes | 1.3359 [1.3231,1.3690] | 0.9483 [0.9375,0.9662] |
| macos-15-0 | scan | 9.0145 [8.8647,9.1562] | 9.0001 [8.7438,9.2778] |
| macos-15-0 | builder | 2.5274 [2.5033,2.5638] | 3.3194 [3.2684,3.3741] |
| macos-15-0 | immutable | 1.3387 [1.3256,1.3516] | 22.7022 [22.4180,22.9255] |
| macos-15-1 | lcg | 1.8508 [1.8310,1.8842] | 1.5973 [1.5668,1.6108] |
| macos-15-1 | primes | 1.3741 [1.3541,1.4104] | 0.9629 [0.9343,0.9878] |
| macos-15-1 | scan | 8.8510 [8.6680,8.9656] | 8.8140 [8.7111,8.8956] |
| macos-15-1 | builder | 2.5195 [2.4955,2.5341] | 3.2851 [3.2471,3.3191] |
| macos-15-1 | immutable | 1.3400 [1.3332,1.3484] | 22.7332 [22.3454,23.3773] |
| ubuntu-24.04-0 | lcg | 1.0000 [0.9997,1.0005] | 1.8551 [1.8545,1.8555] |
| ubuntu-24.04-0 | primes | 1.2396 [1.2382,1.2416] | 1.2544 [1.2501,1.2561] |
| ubuntu-24.04-0 | scan | 2.6399 [2.6353,2.6485] | 2.4281 [2.4257,2.4311] |
| ubuntu-24.04-0 | builder | 1.3846 [1.3769,1.3960] | 1.6668 [1.6592,1.6744] |
| ubuntu-24.04-0 | immutable | 1.1789 [1.1739,1.1805] | 26.0343 [25.9672,26.0819] |
| ubuntu-24.04-1 | lcg | 1.0000 [0.9995,1.0005] | 1.8544 [1.8537,1.8553] |
| ubuntu-24.04-1 | primes | 1.2385 [1.2374,1.2398] | 1.2531 [1.2520,1.2553] |
| ubuntu-24.04-1 | scan | 2.6309 [2.6285,2.6347] | 2.4267 [2.4255,2.4303] |
| ubuntu-24.04-1 | builder | 1.3913 [1.3847,1.3958] | 1.6587 [1.6484,1.6619] |
| ubuntu-24.04-1 | immutable | 1.1706 [1.1667,1.1720] | 26.4264 [26.3962,26.5325] |
| windows-2022-0 | lcg | 0.9976 [0.9951,1.0015] | 1.6203 [1.6163,1.6248] |
| windows-2022-0 | primes | 1.0172 [1.0076,1.0294] | 1.3800 [1.3659,1.4025] |
| windows-2022-0 | scan | 10.2403 [10.0873,10.3580] | 3.9496 [3.9032,4.1259] |
| windows-2022-0 | builder | 1.8070 [1.7950,1.8162] | 1.5765 [1.5656,1.5848] |
| windows-2022-0 | immutable | 1.3874 [1.3845,1.3890] | 72.1499 [71.9009,72.5125] |
| windows-2022-1 | lcg | 1.0001 [0.9993,1.0007] | 1.8572 [1.8564,1.8580] |
| windows-2022-1 | primes | 1.0189 [1.0169,1.0206] | 1.2704 [1.2675,1.2723] |
| windows-2022-1 | scan | 4.4158 [4.4116,4.4178] | 2.3542 [2.3525,2.3571] |
| windows-2022-1 | builder | 1.5607 [1.5517,1.5667] | 1.4976 [1.4911,1.5082] |
| windows-2022-1 | immutable | 1.5543 [1.5493,1.5559] | 77.8607 [77.2356,78.3209] |

The periodic scan version improves the current compiler on every tested platform and passes Rust 1.10. It gains about 9× on macOS, 4.4–10.2× on Windows and 2.6× on Linux. Builder also improves against the current compiler and exceeds Rust 1.10 in all native jobs. The LCG range guard benefits Apple M1; other platforms stay near the current compiler. Positive reciprocal/inlining improves x86 prime throughput, but macOS prime remains about 0.95–0.96 of Rust with upper intervals below 1.10. The complete target is therefore still unachieved.

These gains cannot be reported as a shipped compiler success. A general, name-independent AST proof/lowering and unchanged compiler remeasurement are required. The useful LCG transformation is being moved into the compiler, and the remaining bounded modular-power precision candidate is measured separately in run 38348975326. All rejected/negative observations remain in the ledger and raw archives.
