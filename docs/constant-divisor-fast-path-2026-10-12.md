# Constant divisor fast-path experiment

The compiler candidate emitted a direct C `/` or `%` when the right operand was a nonzero integer literal other than `-1`; remainder was limited to expressions conservatively known to be integer. Dynamic divisors, zero, and `-1` stayed on the checked helper path. The generated-C patch is preserved for reproduction, but the change was rejected because one representative workload regressed.

The frozen comparison used 24 position-balanced pairs per workload and one shared Rust control. The compiler baseline is `4bdd4ec`; all fixture, runtime, stdlib, header, binary, and generated-C hashes plus every correctness check, prewarm, and sample are in the raw JSON. The candidate was built from the same SDK and fixtures with the attached compiler diff. Native arithmetic regression tests passed for O0/O3 UBSan and JavaScript before the measurement.

| Workload | Baseline Forge/Rust (95% CI) | Candidate Forge/Rust (95% CI) | Baseline/candidate throughput (95% CI) | Decision |
| --- | ---: | ---: | ---: | --- |
| lcg | 1.0043 [0.9980, 1.0073] | 1.0007 [0.9968, 1.0069] | 0.9973 [0.9941, 1.0052] | no supported gain |
| primes | 1.0100 [1.0043, 1.0131] | 1.0117 [1.0091, 1.0156] | 1.0018 [0.9984, 1.0032] | no supported gain |
| scan | 1.9445 [1.8929, 1.9807] | 1.9329 [1.8979, 1.9537] | 0.9899 [0.9835, 1.0087] | no supported gain |
| builder | 1.1180 [0.9816, 1.1988] | 0.8599 [0.8216, 1.0045] | 0.8616 [0.7878, 0.9415] | reject: regression |
| immutable | 17.4872 [9.1373, 18.3054] | 10.9555 [9.6518, 17.7587] | 1.0028 [0.9528, 1.1012] | no supported gain |

The clearest result is builder: candidate throughput was 0.8599 of Rust versus 1.1180 for baseline, and paired baseline/candidate throughput was 0.8616 [0.7878, 0.9415]. The fast path was rejected; no source change remains in Forge. Other rows did not show a consistent improvement. This is evidence for these frozen workloads and this host, not a general statement about all constant divisors.

All raw samples and hashes: [constant-divisor-fast-path-2026-10-12.json](constant-divisor-fast-path-2026-10-12.json). Reproduction patch: [constant-divisor-fast-path-2026-10-12.patch](constant-divisor-fast-path-2026-10-12.patch).
