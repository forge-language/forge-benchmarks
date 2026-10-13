# Native range-kernel screening: selective gain, incomplete target

This is a generated-C experiment on compiler d4c632b, compared with original checkpoint 9f70e9d and matched Rust. It does not measure a new compiler release, and cannot isolate incremental change from d4c632b. All six native jobs in [run 38341649774](https://github.com/forge-language/forge-benchmarks/actions/runs/38341649774) completed, with 720 direct checks, 5400 prewarms and 5400 measured executions matching independent references.

| Platform / repeat | Workload | Candidate / old Forge (95% interval) | Candidate / Rust (95% interval) |
| --- | --- | ---: | ---: |
| macos-15-0 | lcg | 1.8934 [1.8376,1.9774] | 1.6537 [1.5948,1.7053] |
| macos-15-0 | primes | 0.9935 [0.9825,1.0069] | 0.9389 [0.9317,0.9522] |
| macos-15-0 | scan | 1.0013 [0.9931,1.0125] | 0.9970 [0.9880,1.0098] |
| macos-15-0 | builder | 2.3034 [2.2575,2.3376] | 1.2958 [1.2296,1.3135] |
| macos-15-0 | immutable | 1.0021 [0.9862,1.0346] | 18.8709 [17.4569,19.7551] |
| macos-15-1 | lcg | 1.8665 [1.8254,1.9307] | 1.6199 [1.5760,1.6772] |
| macos-15-1 | primes | 0.9864 [0.9806,0.9945] | 0.9366 [0.9279,0.9463] |
| macos-15-1 | scan | 0.9988 [0.9896,1.0089] | 1.0013 [0.9837,1.0168] |
| macos-15-1 | builder | 2.0863 [2.0293,2.1753] | 1.2535 [1.1915,1.3064] |
| macos-15-1 | immutable | 1.0155 [0.9907,1.0298] | 17.9486 [16.9930,18.8428] |
| ubuntu-24.04-0 | lcg | 1.0007 [0.9993,1.0043] | 1.6233 [1.6202,1.6251] |
| ubuntu-24.04-0 | primes | 1.0363 [1.0305,1.0406] | 1.2524 [1.2476,1.2606] |
| ubuntu-24.04-0 | scan | 1.0011 [0.9950,1.0031] | 0.8110 [0.8082,0.8144] |
| ubuntu-24.04-0 | builder | 1.2924 [1.2886,1.2987] | 1.2211 [1.2170,1.2258] |
| ubuntu-24.04-0 | immutable | 0.9973 [0.9935,1.0011] | 18.5790 [18.4729,18.6578] |
| ubuntu-24.04-1 | lcg | 0.9992 [0.9952,1.0057] | 1.6265 [1.6191,1.6300] |
| ubuntu-24.04-1 | primes | 1.0404 [1.0333,1.0450] | 1.2615 [1.2536,1.2669] |
| ubuntu-24.04-1 | scan | 1.0035 [1.0006,1.0080] | 0.8136 [0.8088,0.8163] |
| ubuntu-24.04-1 | builder | 1.2948 [1.2931,1.2984] | 1.2241 [1.2207,1.2268] |
| ubuntu-24.04-1 | immutable | 1.0002 [0.9927,1.0058] | 18.8401 [18.7375,18.9570] |
| windows-2022-0 | lcg | 1.0003 [0.9996,1.0007] | 1.6736 [1.6726,1.6744] |
| windows-2022-0 | primes | 1.0592 [1.0581,1.0617] | 1.1778 [1.1746,1.1807] |
| windows-2022-0 | scan | 0.9707 [0.9690,0.9725] | 0.6456 [0.6396,0.6525] |
| windows-2022-0 | builder | 1.2744 [1.2712,1.2788] | 0.9546 [0.9513,0.9564] |
| windows-2022-0 | immutable | 0.9968 [0.9929,1.0018] | 68.6906 [68.2821,69.0115] |
| windows-2022-1 | lcg | 1.0003 [0.9998,1.0007] | 1.8575 [1.8561,1.8582] |
| windows-2022-1 | primes | 1.0372 [1.0359,1.0393] | 1.2175 [1.2155,1.2196] |
| windows-2022-1 | scan | 0.9374 [0.9365,0.9390] | 0.4994 [0.4990,0.4996] |
| windows-2022-1 | builder | 1.2808 [1.2796,1.2821] | 0.9469 [0.9462,0.9482] |
| windows-2022-1 | immutable | 0.9867 [0.9850,0.9878] | 49.4404 [49.1941,49.6308] |

The guarded LCG version gains 1.87–1.89× old Forge on Apple M1 and reaches 1.62–1.65× Rust. Linux/Windows LCG changes are near zero versus the original checkpoint. Positive-range hardware modular power restores the macOS prime regression but still reaches only 0.937–0.939× Rust; the local AMD BC-250 smoke also fails the prime target. The weighted unroll hint fails to solve scan: Windows scan even regresses to about 0.937–0.971× old Forge and remains 0.499–0.646× Rust. Those negative observations are retained. The composite is not adopted as a compiler feature.

The next explicitly labelled prototype combines the useful range guard with architecture-selected positive remainder and a guarded 13-byte periodic dot product. It will compare against unmodified current compiler d4c632b, keeping the old checked bodies for all excluded inputs. Its proof/measurement remains separate; no result is credited to the shipped compiler before integration and remeasurement.
