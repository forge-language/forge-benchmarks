/* Finite native/coroutine dispatch workload; process affinity is set externally. */
#define _GNU_SOURCE
#include "forge_runtime.h"
#include "forge/thread.h"
#include <dirent.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static uint64_t now(clockid_t clock) {
    struct timespec t;
    if (clock_gettime(clock, &t)) exit(20);
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + t.tv_nsec;
}
static void masks(void) {
    DIR *dir = opendir("/proc/self/task");
    if (!dir) exit(21);
    struct dirent *entry;
    while ((entry = readdir(dir))) {
        char *end;
        long tid = strtol(entry->d_name, &end, 10);
        if (*end || tid <= 0) continue;
        cpu_set_t set;
        if (sched_getaffinity((pid_t)tid, sizeof(set), &set)) exit(22);
        fprintf(stderr, "affinity:%ld=", tid);
        for (int i = 0; i < CPU_SETSIZE; i++) if (CPU_ISSET(i, &set)) fprintf(stderr, "%d,", i);
        fputc('\n', stderr);
    }
    closedir(dir);
}
typedef struct {
    uint64_t input, result, submitted, latency;
    unsigned steps;
    atomic_int seen;
    int timed;
} item_t;
typedef struct { _Alignas(64) uint64_t jobs; } stat_t;
static stat_t stats[128];
static atomic_size_t done, warm_done;
static atomic_uint next_slot;
static _Thread_local unsigned slot = 128;
static fr_mutex_t *warm_lock;
static fr_cond_t *warm_cond;
static int warm_entered, warm_release;
static uint64_t reference(uint64_t x, unsigned steps) {
    for (unsigned i = 0; i < steps; i++) x = x * UINT64_C(6364136223846793005) + UINT64_C(1442695040888963407);
    return x;
}
static void job(void *arg) {
    item_t *p = arg;
    if (atomic_fetch_add(&p->seen, 1)) exit(23);
    if (slot == 128) {
        slot = atomic_fetch_add(&next_slot, 1);
        if (slot >= 128) exit(24);
    }
    if (!p->timed) {
        fr_mutex_lock(warm_lock);
        warm_entered++;
        fr_cond_broadcast(warm_cond);
        while (!warm_release) fr_cond_wait(warm_cond, warm_lock);
        fr_mutex_unlock(warm_lock);
    }
    p->result = reference(p->input, p->steps);
    if (p->timed) {
        p->latency = now(CLOCK_MONOTONIC) - p->submitted;
        stats[slot].jobs++;
    }
    atomic_fetch_add_explicit(p->timed ? &done : &warm_done, 1, memory_order_release);
}
typedef struct { item_t *item; int yielded; atomic_int executing; } coro_item_t;
static fr_coro_status_t coro_job(fr_coro_t *coro, void *arg) {
    coro_item_t *s = arg;
    if (atomic_fetch_add(&s->executing, 1)) exit(25);
    if (!s->yielded) {
        s->yielded = 1;
        atomic_fetch_sub(&s->executing, 1);
        return fr_yield(coro);
    }
    job(s->item);
    atomic_fetch_sub(&s->executing, 1);
    return FR_CORO_DONE;
}
static atomic_int parked_done;
static fr_coro_status_t parked(fr_coro_t *coro, void *arg) {
    (void)arg;
    fr_msg_t message;
    if (!fr_try_recv(fr_coro_process(coro), &message)) return FR_CORO_WAITING_RECV;
    if (message.tag != 71 || message.value != 29) exit(26);
    fr_msg_free_payload(&message);
    atomic_fetch_add(&parked_done, 1);
    return FR_CORO_DONE;
}
#ifdef FORGE_DISPATCH_INSTRUMENT
#include "work_queue.h"
static atomic_int observation_window;
static atomic_size_t queue_probes;
fr_coro_t *__real_fr_run_queue_pop(fr_run_queue_t *);
fr_coro_t *__real_fr_run_queue_steal(fr_run_queue_t *, fr_run_queue_t *);
fr_coro_t *__wrap_fr_run_queue_pop(fr_run_queue_t *q) {
    if (atomic_load(&observation_window)) atomic_fetch_add(&queue_probes, 1);
    return __real_fr_run_queue_pop(q);
}
fr_coro_t *__wrap_fr_run_queue_steal(fr_run_queue_t *victim, fr_run_queue_t *thief) {
    if (atomic_load(&observation_window)) atomic_fetch_add(&queue_probes, 1);
    return __real_fr_run_queue_steal(victim, thief);
}
#endif
static int compare(const void *a, const void *b) {
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return (x > y) - (x < y);
}
int main(int argc, char **argv) {
    if (argc != 6) return 2;
    const char *mode = argv[1];
    if (strcmp(mode, "native") && strcmp(mode, "blocked") && strcmp(mode, "coro") && strcmp(mode, "mixed")) return 12;
    int requested = atoi(argv[2]);
    size_t count = strtoull(argv[3], NULL, 10);
    unsigned steps = (unsigned)strtoul(argv[4], NULL, 10);
    uint64_t seed = strtoull(argv[5], NULL, 10);
    if (requested < 1 || requested > 128 || count < 1 || count > 10000000 || steps > 1000000) return 3;
    item_t *items = calloc(count, sizeof(*items));
    uint64_t *latencies = malloc(count * sizeof(*latencies));
    if (!items || !latencies) return 4;
    warm_lock = fr_mutex_create(); warm_cond = fr_cond_create();
    if (!warm_lock || !warm_cond) return 11;
    for (size_t i = 0; i < count; i++) {
        items[i].input = seed + i; items[i].steps = steps; items[i].timed = 1;
        atomic_init(&items[i].seen, 0);
    }
    uint64_t total = now(CLOCK_MONOTONIC), total_cpu = now(CLOCK_PROCESS_CPUTIME_ID);
    fr_scheduler_t *s = fr_scheduler_create(requested);
    if (!s) return 5;
    int workers = fr_scheduler_worker_count(s);
    if (workers < 1 || workers > 128) return 6;
    enum { PARKED = 32 };
    fr_process_t *parked_processes[PARKED] = {0};
    if (!strcmp(mode, "blocked")) for (int i = 0; i < PARKED; i++) {
        parked_processes[i] = fr_process_create("parked-dispatch");
        if (!parked_processes[i]) return 13;
        fr_scheduler_add_process(s, parked_processes[i]);
        if (!fr_coro_spawn(parked_processes[i], parked, NULL, 0)) return 14;
    }
    fr_scheduler_start(s);
    item_t warm[128] = {0};
    for (int i = 0; i < workers; i++) {
        atomic_init(&warm[i].seen, 0);
        warm[i].input = i; warm[i].steps = 1;
        if (fr_sched_pool_submit(s, job, &warm[i])) return 7;
    }
    fr_mutex_lock(warm_lock);
    while (warm_entered != workers) fr_cond_wait(warm_cond, warm_lock);
    fr_mutex_unlock(warm_lock);
    size_t coro_count = !strcmp(mode, "coro") ? count : (!strcmp(mode, "mixed") ? count / 2 : 0);
    if (coro_count) {
        fr_process_t *process = fr_process_create("compute-dispatch");
        if (!process) return 15;
        fr_scheduler_add_process(s, process);
        for (size_t i = 0; i < coro_count; i++) {
            coro_item_t *state = calloc(1, sizeof(*state));
            if (!state) return 16;
            state->item = &items[i]; atomic_init(&state->executing, 0);
            if (!fr_coro_spawn(process, coro_job, state, sizeof(*state))) return 17;
        }
    }
    masks();
    uint64_t wall = now(CLOCK_MONOTONIC), cpu = now(CLOCK_PROCESS_CPUTIME_ID);
    for (size_t i = 0; i < coro_count; i++) items[i].submitted = wall;
#ifdef FORGE_DISPATCH_INSTRUMENT
    atomic_store(&observation_window, 1);
#endif
    fr_mutex_lock(warm_lock);
    warm_release = 1;
    fr_cond_broadcast(warm_cond);
    fr_mutex_unlock(warm_lock);
    for (size_t i = coro_count; i < count; i++) {
        items[i].submitted = now(CLOCK_MONOTONIC);
        if (fr_sched_pool_submit(s, job, &items[i])) return 8;
    }
    while (atomic_load_explicit(&done, memory_order_acquire) != count) fr_thread_yield();
    fr_scheduler_stop(s);
    cpu = now(CLOCK_PROCESS_CPUTIME_ID) - cpu;
    wall = now(CLOCK_MONOTONIC) - wall;
#ifdef FORGE_DISPATCH_INSTRUMENT
    atomic_store(&observation_window, 0);
    fprintf(stderr, "queue_probes=%zu\n", atomic_load(&queue_probes));
#endif
    if (fr_sched_pool_queued(s) != 0 || atomic_load(&warm_done) != (size_t)workers) return 18;
    /* Wake parked coroutines after the timed native phase; prove progress and
     * ownership transitions without counting that cleanup as native throughput. */
    for (int i = 0; i < PARKED && parked_processes[i]; i++)
        if (!fr_send(parked_processes[i], 71, 29, NULL, 0)) return 19;
    if (parked_processes[0]) {
        fr_scheduler_run(s);
        if (atomic_load(&parked_done) != PARKED) return 27;
    }
    fr_scheduler_destroy(s);
    total_cpu = now(CLOCK_PROCESS_CPUTIME_ID) - total_cpu;
    total = now(CLOCK_MONOTONIC) - total;
    uint64_t checksum = 0, completed = 0;
    for (size_t i = 0; i < count; i++) {
        if (atomic_load(&items[i].seen) != 1 || items[i].result != reference(items[i].input, steps)) return 9;
        checksum += items[i].result;
        latencies[i] = items[i].latency;
    }
    for (int i = 0; i < workers; i++) completed += stats[i].jobs;
    if (completed != count) return 10;
    qsort(latencies, count, sizeof(*latencies), compare);
    printf("{\"mode\":\"%s\",\"coro_count\":%zu,\"requested\":%d,\"workers\":%d,\"count\":%zu,\"steps\":%u,\"seed\":%llu,\"checksum\":%llu,\"wall_ns\":%llu,\"cpu_ns\":%llu,\"total_ns\":%llu,\"total_cpu_ns\":%llu,\"p50_ns\":%llu,\"p95_ns\":%llu,\"p99_ns\":%llu,\"per_worker_jobs\":[",
           mode, coro_count, requested, workers, count, steps, (unsigned long long)seed, (unsigned long long)checksum,
           (unsigned long long)wall, (unsigned long long)cpu, (unsigned long long)total, (unsigned long long)total_cpu,
           (unsigned long long)latencies[count / 2], (unsigned long long)latencies[count * 95 / 100],
           (unsigned long long)latencies[count * 99 / 100]);
    for (int i = 0; i < workers; i++) printf("%s%llu", i ? "," : "", (unsigned long long)stats[i].jobs);
    puts("]}");
    free(latencies); free(items);
    fr_cond_destroy(warm_cond); fr_mutex_destroy(warm_lock);
    return 0;
}
