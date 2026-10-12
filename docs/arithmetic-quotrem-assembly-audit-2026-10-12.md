# Shared quotient/remainder assembly audit

The dynamic-divisor diagnostic computes both `value / b` and `value % b` from the same pure locals in each iteration (`benchmark/arithmetic/kernels.fg`). A compiler-level common quotient/remainder lowering would only be worthwhile if GCC emitted two hardware divisions.

The current Forge candidate executable was built by `benchmark/arithmetic_compare.py --build-only --workloads mixed64` from the generated C in `/tmp/forge-divrem-audit-20261012/snapshot/candidate.c`. Its SHA-256 is `aeeac46542cdf4aa3cc08c0396955579fa8d68ec99fe5be72ceb3508eb5193c7`; generated C SHA-256 is `1ec224e55a382e0d81c99c954147ba1956906b5a08d66c9dc9151731b6cb5776`.

In the positive-divisor hot loop, GCC emits one `idiv rcx` per iteration at `0x2655`. It consumes the quotient from `rax` and the remainder from `rdx` in the following instructions. The alternate signed path likewise emits one `idiv rcx` at `0x26f9` and uses both outputs. The same check is visible in the generated C as `FORGE_ADD(FORGE_ADD(total, FORGE_DIV(value, b)), FORGE_MOD(value, b))`; LTO has inlined the helpers and combined the operations. The hypothesis of duplicate division work is therefore false for this fixture, and no compiler change is warranted.

Reproduce the build with:

```sh
python3 benchmark/arithmetic_compare.py \
  --forge-root /home/helloworld0822/coding/forge \
  --forge /home/helloworld0822/coding/forge/build/bin/forge \
  --build-dir /tmp/forge-divrem-audit-20261012 \
  --output /tmp/forge-divrem-audit-20261012.json \
  --build-only --workloads mixed64
objdump -d -Mintel /tmp/forge-divrem-audit-20261012/candidate
```

This is a static code-generation finding, not a throughput measurement. The existing [dynamic divisor comparison](arithmetic-division-2026-10-12.md) remains the performance evidence; its checked narrowing prototypes regressed or stayed at parity.
