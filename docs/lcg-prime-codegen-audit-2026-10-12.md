# LCG and prime-search code-generation audit

This is a static code-generation investigation, not a timing run. It used Forge
`368b9c8` (`build/bin/forge`, SHA-256
`81233d6057f716a851813b77b5fd046a5d5fd74b6d9d082cd45075b3d887aaba`) and
the checked-in `benchmark/cpu/kernels.fg` and `.rs` fixtures. The generated C
and assembly were built with GCC 13.3.0 `-O3 -DNDEBUG -march=native`; Rust
assembly used rustc 1.98.1 `-C opt-level=3 -C target-cpu=native`. The generated
C was SHA-256 `1b8bcdc9e104ca23e54af8e116fb3d98139851248d114c5a5d1f6023ccef3305`.

In LCG, Forge's generated C lowers the positive constant remainder directly,
while wrapping multiplication remains behind the inline `FORGE_MUL` helper.
GCC folds that helper and emits a reciprocal-multiply/shift sequence for `%
2147483647`. Rust emits the same constant-multiply and reciprocal-remainder
sequence. The Forge loop counts upward; Rust counts the inner loop downward.
This evidence does not expose a large arithmetic gap for the current LCG
fixture, consistent with the repeated paired measurements near parity. It does
not support replacing the already-rejected Mersenne-fold candidate.

In prime search, the generated Forge C uses the checked dynamic remainder
expression. GCC's assembly uses `idivq` for the trial-divisor operation. Rust
uses a `divl` fast path when both the candidate value and divisor fit unsigned
32 bits, with an `idivq` fallback. This is a concrete code-generation
difference, but a previous Forge prototype that split out a guarded signed
32-bit trial-division path did not improve throughput: its paired
candidate/baseline ratio was 0.9973 [0.9896, 1.0024]. The narrow path should
not be repeated without a new way to remove or amortize its guard cost.

All 21 Forge CTest suites passed after rebuilding the current source. Static
assembly cannot predict end-to-end timing, so these findings guide future
experiments but do not establish a speedup. An OMO delegated review was
attempted with both configured models (`glm-5.3-flash` and `qwen3.8-flash`),
but the provider returned repeated API connection failures before producing a
subagent result; no OMO findings are claimed.
