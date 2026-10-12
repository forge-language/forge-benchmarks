#define _GNU_SOURCE
#include "forge/event.h"

#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/eventfd.h>
#include <unistd.h>

extern int64_t bench_clock_ns(void);

static uintptr_t observed;
static int callback_count;

static void observe_event(fr_event_loop_t *loop, int fd, uint32_t events, void *userdata) {
    (void)loop;
    (void)fd;
    (void)events;
    observed = (uintptr_t)userdata;
    callback_count++;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    char *end = NULL;
    uint64_t operations = strtoull(argv[1], &end, 10);
    if (!end || *end || operations == 0 || operations > 100000000) return 2;

    int fd = eventfd(0, EFD_NONBLOCK | EFD_CLOEXEC);
    if (fd < 0) return 3;
    fr_event_loop_t *loop = fr_event_loop_create();
    if (!loop) return 4;
    fr_event_loop_set_cb(loop, observe_event);
    if (fr_event_loop_add(loop, fd, FR_EVENT_READ, NULL) != 0) return 5;

    int64_t start = bench_clock_ns();
    for (uint64_t i = 1; i <= operations; i++) {
        if (fr_event_loop_mod(loop, fd, FR_EVENT_READ, (void *)(uintptr_t)i) != 0) return 6;
    }
    int64_t elapsed = bench_clock_ns() - start;

    uint64_t signal = 1;
    if (write(fd, &signal, sizeof(signal)) != (ssize_t)sizeof(signal)) return 7;
    if (fr_event_loop_poll(loop, 1000) != 1 || callback_count != 1 || observed != operations) return 8;
    printf("%" PRId64 " %" PRIu64 "\n", elapsed, operations);
    fr_event_loop_destroy(loop);
    close(fd);
    return 0;
}
