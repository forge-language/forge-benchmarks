/* Common measurement counters only; no workload algorithm is implemented here. */
#include <stdatomic.h>
#include <stdint.h>
static _Atomic int64_t completed;
static _Atomic int64_t total;
void bench_reset(void) { atomic_store(&completed, 0); atomic_store(&total, 0); }
void bench_result(int64_t value) {
    atomic_fetch_add_explicit(&total, value, memory_order_relaxed);
    atomic_fetch_add_explicit(&completed, 1, memory_order_relaxed);
}
int64_t bench_count(void) { return atomic_load(&completed); }
int64_t bench_total(void) { return atomic_load(&total); }
