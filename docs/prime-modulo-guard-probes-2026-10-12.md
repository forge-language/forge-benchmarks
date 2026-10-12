# Dynamic remainder guard probes

Two compiler-only candidates added a runtime fast path to `__forge_mod_i64`, while keeping the original checked signed fallback. Both were measured against frozen current Forge and Rust prime kernels in 48 randomized groups balanced over all six execution orders. The 160 direct reference cases, 144 same-input prewarms and 144 measurements passed for each candidate.

The first candidate used a 32-bit unsigned remainder when `0 <= a <= UINT32_MAX` and `0 < b <= UINT32_MAX`. Its baseline/candidate Forge throughput ratio was 0.9878 [0.9862, 0.9905], a statistically supported regression. The second used 64-bit unsigned remainder when `a >= 0 && b > 0`; baseline/candidate was 0.9893 [0.9872, 0.9918], also a regression. Both were discarded and the compiler source was restored to its original state.

The first candidate's generated executable contained both `div %ebp` and `idiv %rbp`; the second contained unsigned `div %rdi` and signed `idiv %r8`. Avoiding the checked helper did not compensate for runtime guards and a wide divide in this workload. The first candidate build passed all 21 CTest suites; both candidates passed all 160 benchmark reference cases.

The exact candidate forms were:

```c
if (a >= 0 && (uint64_t)a <= UINT32_MAX && b > 0 &&
    (uint64_t)b <= UINT32_MAX)
    return (int64_t)((uint32_t)a % (uint32_t)b);
__forge_check_div_i64(a, b);
return a % b;
```

and:

```c
if (a >= 0 && b > 0) return (int64_t)((uint64_t)a % (uint64_t)b);
__forge_check_div_i64(a, b);
return a % b;
```

- [32-bit guard raw measurements](prime-mod-uint32-guard-2026-10-12.json)
- [positive 64-bit guard raw measurements](prime-mod-positive-guard-2026-10-12.json)
- [current prime baseline report](cpu-current-all-2026-10-12.md)
