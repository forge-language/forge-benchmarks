# Positive constant division lowering audit

The native backend now emits a direct C `/` for a known-integer left operand and a positive integer-literal divisor. Other divisions still use Forge's checked helper. The existing positive-literal remainder path uses the same restriction.

The guard excludes both checked failure cases: divisor zero and `INT64_MIN / -1`. Thus `a / c` for `c > 0` has the same truncation-toward-zero result for every signed 64-bit `a`, including `INT64_MIN`; the C expression has no signed-division undefined case. Both expressions retain the same operand expressions and evaluate each once.

Added an arithmetic regression over signed boundaries and values around multiples of seven. It runs generated C under UBSan at `-O0` and `-O3` and checks the JavaScript backend. The arithmetic regression passed, and the full CTest suite had 22/22 passing after the codegen change (the new test was then rerun separately and passed).

This does **not** establish a release-mode speedup. With GCC 13.3 `-O3`, the helper form `__forge_div_i64(a, 7)` and direct form `a / 7` produced identical x86-64 instruction sequences because GCC already inlines the helper and removes its proven-dead checks. The change reduces emitted C and avoids depending on that optimization for lower optimization levels or other native C compilers; it is not counted toward the Rust 1.10× target.

An OMO Sisyphus-Junior reviewer suggested extending the positive-literal check elision to division. Its task ID is `ses_ecd9ca1a1ffemKBJ2u3GYQWlhL`. The reviewer could not access the benchmark fixtures from the Forge repository; the fixture and generated-code checks were performed separately.
