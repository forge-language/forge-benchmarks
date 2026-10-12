#define _GNU_SOURCE
#include "forge/event.h"

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/eventfd.h>
#include <unistd.h>

extern int64_t bench_clock_ns(void);

static uint8_t *seen;
static uint32_t event_count;
static uint32_t observed;

static void mark_ready(fr_event_loop_t *loop, int fd, uint32_t events, void *userdata) {
    (void)loop;
    (void)fd;
    (void)events;
    uintptr_t index = (uintptr_t)userdata;
    if (index < event_count && !seen[index]) {
        seen[index] = 1;
        observed++;
    }
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    char *end = NULL;
    unsigned long parsed = strtoul(argv[1], &end, 10);
    if (!end || *end || parsed == 0 || parsed > 65536) return 2;
    event_count = (uint32_t)parsed;
    int *fds = malloc((size_t)event_count * sizeof(*fds));
    seen = calloc(event_count, sizeof(*seen));
    if (!fds || !seen) return 3;
    fr_event_loop_t *loop = fr_event_loop_create();
    if (!loop) return 4;
    fr_event_loop_set_cb(loop, mark_ready);

    for (uint32_t i = 0; i < event_count; i++) {
        fds[i] = eventfd(0, EFD_NONBLOCK | EFD_CLOEXEC);
        if (fds[i] < 0 || fr_event_loop_add(loop, fds[i], FR_EVENT_READ,
                                             (void *)(uintptr_t)i) != 0) return 5;
    }
    uint64_t signal = 1;
    for (uint32_t i = 0; i < event_count; i++)
        if (write(fds[i], &signal, sizeof(signal)) != (ssize_t)sizeof(signal)) return 6;

    uint64_t poll_calls = 0;
    int64_t start = bench_clock_ns();
    while (observed < event_count) {
        int n = fr_event_loop_poll(loop, 0);
        if (n <= 0) return 7;
        poll_calls++;
    }
    int64_t elapsed = bench_clock_ns() - start;
    printf("%" PRId64 " %" PRIu64 " %" PRIu32 "\n", elapsed, poll_calls, observed);
    fr_event_loop_destroy(loop);
    for (uint32_t i = 0; i < event_count; i++) close(fds[i]);
    free(fds);
    free(seen);
    return 0;
}
