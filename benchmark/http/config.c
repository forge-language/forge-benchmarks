#define _GNU_SOURCE
#include <errno.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>

/* Configuration only. No sockets, HTTP processing, or benchmark timing. */
static int configured_cpus[64];
static int configured_count;
void bench_config(void) {
    const char *text = getenv("FORGE_BENCH_CPUS");
    if (!text || !*text) abort();
    configured_count = 0;
    while (*text) {
        char *end = NULL;
        errno = 0;
        long cpu = strtol(text, &end, 10);
        if (end == text || errno || cpu < 0 || cpu >= CPU_SETSIZE ||
            configured_count >= 64) abort();
        configured_cpus[configured_count++] = (int)cpu;
        if (!*end) break;
        if (*end != ',' || !end[1]) abort();
        text = end + 1;
    }
}
void bench_pin_worker(int index) {
    if (index < 0 || index >= configured_count) abort();
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(configured_cpus[index], &set);
    if (sched_setaffinity(0, sizeof(set), &set) != 0) {
        perror("benchmark worker affinity");
        abort();
    }
}
/* Forge's native API requests absolute IDs 0..workers-1. Remap only this
 * configuration request; preserve its existing HTTP algorithm and policy. */
void __wrap_fr_thread_pin_cpu(int index) { bench_pin_worker(index); }
