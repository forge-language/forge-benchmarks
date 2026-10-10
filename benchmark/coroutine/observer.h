#ifndef FORGE_BENCH_COROUTINE_OBSERVER_H
#define FORGE_BENCH_COROUTINE_OBSERVER_H
#include <stdint.h>
void bench_config(int argc, const char *const *argv);
int64_t bench_arg(int64_t index);
void bench_prepare(void);
int64_t bench_clock_ns(void);
int64_t bench_observe_i64(int64_t value);
void bench_result(int64_t id, int64_t value);
int bench_finish(int64_t start);
#endif
