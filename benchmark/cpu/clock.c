/* Shared OS timer only. All benchmark algorithms live in .fg / .rs. */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdlib.h>
#include <time.h>
int64_t bench_clock_ns(void) {
 struct timespec now;
 if(clock_gettime(CLOCK_MONOTONIC,&now))abort();
 return (int64_t)now.tv_sec*1000000000+now.tv_nsec;
}

/* Equal one-shot optimization barriers for both implementations, outside the
 * inner loops. They prevent loop hoisting across the timer without adding a
 * black_box or volatile access to every data operation. */
__attribute__((noinline)) int64_t bench_observe_i64(int64_t value) {
 __asm__ __volatile__("" : "+r"(value) : : "memory");
 return value;
}
