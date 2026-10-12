# Prime modulo machine-code audit

This read-only audit checks whether Forge's checked dynamic remainder helper
adds work to the measured prime-search loop. It uses the checked-in source
matched CPU fixture, Forge compiler commit `1994dc41fdef1fe1a3b89b9251f0313a3e36d9e8`,
and the same build path used by `benchmark/cpu_compare.py --build-only
--workloads primes`: GCC 13.3.0 with `-O3 -DNDEBUG -march=native -flto`.

The generated C contains `FORGE_MOD(value, d)` at `snapshot/kernels.c:122`;
the macro calls `__forge_mod_i64`, whose helper calls
`__forge_check_div_i64` to trap on a zero divisor or `INT64_MIN / -1`
(`snapshot/kernels.c:22-26,46`). The optimized Forge executable has one
integer divide instruction. In the prime loop at address `0x2e70`, the hot
path is `mov`, increment `d`, `cqo`, `idiv rbp`, and a remainder-zero test
(`test rdx,rdx`); there is no zero-divisor or signed-overflow check between
the loop's modulo operation and its result test. GCC/LTO has eliminated those
helper checks for this loop.

The corresponding Rust loop at `kernels::main+0x830` first traps if `d == 0`,
then tests whether both operands fit in 32 unsigned bits. It uses `div r9d`
when they do and `idiv r9` as a fallback (`0x1a700-0x1a739`). The observed
code-generation gap is therefore 32-bit unsigned division versus Forge's
64-bit signed division, not checked-helper overhead.

OMO's proposed static range-based removal of modulo trap checks is rejected
for this workload: the generated helper checks are already gone in the final
Forge loop. Its suggested `cg_int_range` hook also cannot currently prove the
loop's dynamic divisor range from local induction variables; it handles
integer literals and supported constant arithmetic expressions, not local
identifiers. The previous runtime unsigned-width guard measurements regressed
(baseline/candidate Forge throughput `0.9878 [0.9862, 0.9905]` for the
32-bit guard), so a new width-specialization proposal would need a materially
different way to avoid repeated guard cost.

This is static assembly evidence, not a timing comparison, and establishes no
performance gain. Reproduction: `python3 benchmark/cpu_compare.py
--build-dir /tmp/forge-prime-audit-current --build-only --workloads primes`,
then inspect the Forge and Rust executables with `objdump -d -Mintel`. The
snapshot records Forge executable SHA-256
`d8feb88ce2be28a738d300c871a908455b7f4ef167a8b6e18c8bbb967fb7e729` and
generated C SHA-256
`6c0e3241d26e9f72528264ec11201fe083b81466d5967954c8d26959c2877c95`.
