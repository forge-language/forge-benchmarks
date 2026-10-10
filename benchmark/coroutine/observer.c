/* Shared measurement/configuration only. Recurrence and yielding are FG/Rust.
 * Result storage verifies task IDs, while Python verifies each stored value.
 * Timer covers observer setup + runtime lifecycle + completion validation.
 * Result printing and observer-buffer teardown happen after the timer. */
#define _POSIX_C_SOURCE 200809L
#include "observer.h"
#include <errno.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
static int64_t config[5];
static _Atomic int64_t *seen;
static int64_t *values;
static _Atomic int errors;
void bench_config(int argc, const char *const *argv) {
    if (argc != 6) abort();
    for (int i = 0; i < 5; ++i) {
        char *end = NULL;
        errno = 0;
        config[i] = strtoll(argv[i + 1], &end, 10);
        if (errno || !end || *end || config[i] <= 0) abort();
    }
    if ((config[0] != 1 && config[0] != 2 && config[0] != 4) ||
        config[1] > 100000 || config[2] > 1000000 || config[3] > 1000000 ||
        config[4] > 1000000) abort();
}
int64_t bench_arg(int64_t index) {
    if (index < 0 || index >= 5) abort();
    return config[index];
}
void bench_prepare(void) {
    seen = calloc((size_t)config[1], sizeof(*seen));
    values = calloc((size_t)config[1], sizeof(*values));
    if (!seen || !values) abort();
    atomic_store(&errors, 0);
    for (int64_t i = 0; i < config[1]; ++i) atomic_init(&seen[i], 0);
}
int64_t bench_clock_ns(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) abort();
    return (int64_t)now.tv_sec * 1000000000 + now.tv_nsec;
}
__attribute__((noinline)) int64_t bench_observe_i64(int64_t value) {
    __asm__ __volatile__("" : "+r"(value) : : "memory");
    return value;
}
void bench_result(int64_t id, int64_t value) {
    if (id < 0 || id >= config[1] || value <= 0 || value >= 2147483647) {
        atomic_store(&errors, 1);
        return;
    }
    // Reserve the result slot before writing, avoiding a race even on duplicate
    // task IDs. Joined runtimes ensure all writes finish before validation.
    if (atomic_fetch_add_explicit(&seen[id], 1, memory_order_relaxed) != 0) {
        atomic_store(&errors, 1);
        return;
    }
    values[id] = value;
}
int bench_finish(int64_t start) {
    int64_t total = 0;
    for (int64_t i = 0; i < config[1]; ++i) {
        if (atomic_load_explicit(&seen[i], memory_order_relaxed) != 1) return 3;
        total += values[i];
    }
    if (atomic_load(&errors)) return 4;
    int64_t elapsed = bench_clock_ns() - start;
    printf("%lld\n%lld\n", (long long)total, (long long)elapsed);
    for (int64_t i = 0; i < config[1]; ++i)
        printf("%s%lld", i ? "," : "", (long long)values[i]);
    putchar('\n');
    free(values); free(seen);
    return 0;
}
