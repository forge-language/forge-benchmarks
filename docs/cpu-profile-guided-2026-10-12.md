# GCC profile-guided optimization probe

The frozen current Forge C output and libraries were compiled with GCC `-O3 -march=native -flto -fprofile-generate`, trained with eight seeds each for the existing LCG and prime workloads, then rebuilt with `-fprofile-use -fprofile-correction`. A 48-pair three-way comparison used baseline Forge, the PGO binary and unchanged Rust, with all six execution orders balanced and a same-input prewarm before every timing.

All 308 direct reference cases, 288 prewarms and 288 measurements matched. LCG baseline/candidate Forge throughput was 1.0047 [0.9959, 1.0076], inconclusive. Prime baseline/candidate was 0.9887 [0.9864, 0.9904], a regression. Rust/candidate was 1.0066 [1.0013, 1.0112] for LCG and 0.9995 [0.9976, 1.0015] for primes. PGO is not adopted; the standard `-O3 -march=native -flto` build remains.

- [Full paired raw data and hashes](cpu-profile-guided-2026-10-12.json)
- [Current baseline build and dimensions](cpu-current-all-2026-10-12.md)
