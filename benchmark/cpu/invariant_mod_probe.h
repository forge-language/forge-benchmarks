#ifndef FORGE_INVARIANT_MOD_PROBE_H
#define FORGE_INVARIANT_MOD_PROBE_H

/* Generated-C experiment, not a shipped compiler/runtime API.
 * The caller computes the descriptor once for an invariant integer divisor.
 * __forge_mod_i64 supplies Forge's existing signed remainder/trap contract. */
typedef struct {
    int64_t divisor;
    uint64_t reciprocal;
} forge_probe_mod_descriptor;

static inline forge_probe_mod_descriptor forge_probe_mod_prepare(int64_t divisor) {
    forge_probe_mod_descriptor result = {divisor, 0};
#if defined(__SIZEOF_INT128__)
    if (divisor > 1)
        result.reciprocal = UINT64_MAX / (uint64_t)divisor + UINT64_C(1);
#endif
    return result;
}

static inline int64_t forge_probe_mod(int64_t value, forge_probe_mod_descriptor descriptor) {
#if defined(__SIZEOF_INT128__)
    if (value >= 0 && descriptor.divisor > 1) {
        uint64_t n = (uint64_t)value, d = (uint64_t)descriptor.divisor;
        uint64_t q = (uint64_t)(((unsigned __int128)n * descriptor.reciprocal) >> 64);
        /* reciprocal = ceil(2^64/d), so q is floor(n/d) or one larger.
         * q*d <= n+d <= 2^64-2 since both n and d are <= INT64_MAX.
         * Thus this product cannot wrap, and one correction is sufficient. */
        uint64_t product = q * d;
        if (product > n) product -= d;
        return (int64_t)(n - product);
    }
#endif
    return __forge_mod_i64(value, descriptor.divisor);
}

#endif
