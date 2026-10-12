# Dynamic integer divisor comparison

Compiler diagnostic microbenchmark. Ratios are elapsed baseline / candidate and Rust / candidate for identical work. A value above 1 means faster candidate throughput.

| Distribution | Baseline ms | Candidate ms | Rust ms | Baseline/candidate median [95% CI] | Rust/candidate median [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: |
| unsigned32 | 44.679 | 45.273 | 45.213 | 0.9869 [0.9860, 0.9881] | 0.9992 [0.9960, 1.0020] |
| negative32 | 46.069 | 46.505 | 45.673 | 0.9906 [0.9901, 0.9913] | 0.9822 [0.9802, 0.9829] |
| mixed32 | 45.359 | 45.793 | 45.268 | 0.9895 [0.9858, 0.9941] | 0.9881 [0.9864, 0.9939] |
| positive64 | 61.465 | 61.485 | 62.057 | 0.9997 [0.9987, 1.0000] | 1.0073 [1.0049, 1.0109] |
| negative64 | 63.009 | 63.001 | 63.735 | 0.9999 [0.9994, 1.0009] | 1.0115 [1.0085, 1.0137] |
| mixed64 | 62.390 | 62.245 | 62.280 | 1.0023 [1.0011, 1.0059] | 1.0007 [0.9997, 1.0046] |

| Distribution | Prototype | Baseline speedup [95% CI] | Rust/prototype [95% CI] |
| --- | --- | ---: | ---: |
| unsigned32 | likely | 0.9826 [0.9816, 0.9843] | 0.9939 [0.9914, 0.9960] |
| negative32 | likely | 0.9823 [0.9820, 0.9839] | 0.9740 [0.9737, 0.9756] |
| mixed32 | likely | 0.9859 [0.9819, 0.9880] | 0.9864 [0.9823, 0.9914] |
| positive64 | likely | 0.9992 [0.9983, 1.0005] | 1.0081 [1.0038, 1.0100] |
| negative64 | likely | 1.0003 [0.9996, 1.0008] | 1.0116 [1.0078, 1.0136] |
| mixed64 | likely | 1.0026 [1.0001, 1.0051] | 1.0002 [0.9995, 1.0041] |

8000000 iterations per sample, 12 measured groups. Protocol: prewarmed position-balanced cyclic rotations; adjacency not fully balanced. Every timed sample follows a same-input prewarm and matches the independent Python signed-integer oracle. All raw samples, warmups, arguments, hashes and compiler commands are retained in the JSON report.

Each iteration calculates signed quotient and remainder of the same dynamic dividend/divisor, accumulates both, advances the dividend by 17 and updates the divisor with (b + 11) % 65521 + 1. Compilers can share quotient/remainder work. Divisors stay positive; negative and mixed distributions vary dividend sign. Narrow magnitudes fit uint32 for all allowed iteration counts; wide magnitudes exceed uint32. This diagnoses narrowing-guard cost and benefit; it does not cover independent divide-only/remainder-only workloads or every divisor distribution.

Both Forge compilers link exactly the same frozen native archives and headers. GCC -O3, native tuning and LTO are matched by Rust opt-level=3, native tuning, thin LTO and one codegen unit; Rust updates explicitly wrap to match Forge. Input/output barriers occur outside the loop. Parser, startup and output time are excluded from kernel timing. RSS is whole-process wait4 information, including possible pre-exec runner footprint; it is not a precise language heap measurement.

Shared-host scheduling/frequency noise remains despite affinity and balanced order. Bootstrap intervals are per-row median estimates from this run and are not family-wise confidence or a universal 110% guarantee. No result is discarded or retried after a checksum failure.
