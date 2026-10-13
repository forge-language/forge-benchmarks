/* Common timer and one-shot barriers; contains no measured algorithm. */
#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include <stdint.h>
#include <stdlib.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
int64_t bench_clock_ns(void) {
    static LARGE_INTEGER frequency, origin;
    static int ready;
    LARGE_INTEGER now;
    if (!ready) {
        if (!QueryPerformanceFrequency(&frequency) || frequency.QuadPart <= 0 ||
            !QueryPerformanceCounter(&origin)) abort();
        ready = 1;
    }
    if (!QueryPerformanceCounter(&now)) abort();
    int64_t ticks = now.QuadPart - origin.QuadPart;
    /* Split seconds before conversion to avoid ticks*1e9 overflow. The
     * fractional result is below 1e9; double rounding is sub-nanosecond. */
    return (ticks / frequency.QuadPart) * INT64_C(1000000000) +
           (int64_t)((double)(ticks % frequency.QuadPart) * 1e9 / (double)frequency.QuadPart);
}
#else
#include <time.h>
int64_t bench_clock_ns(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) abort();
    return (int64_t)now.tv_sec * INT64_C(1000000000) + now.tv_nsec;
}
#endif

__attribute__((noinline)) int64_t bench_observe_i64(int64_t value) {
    __asm__ __volatile__("" : "+r"(value) : : "memory");
    return value;
}
