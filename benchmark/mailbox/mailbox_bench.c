#define _POSIX_C_SOURCE 200809L
#include "forge_runtime.h"
#include <inttypes.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <sched.h>
typedef struct { fr_process_t *process; uint64_t count; atomic_uint_fast64_t *seen; atomic_uint_fast64_t *sum; } worker_t;
static atomic_uint_fast64_t consumed;
static void *consumer(void *arg) {
    worker_t *w = arg;
    for (;;) {
        fr_msg_t msg;
        if (!fr_recv(w->process, &msg)) return (void *)1;
        if (msg.tag == 0) { fr_msg_free_payload(&msg); return NULL; }
        if (msg.tag != 1 || msg.value < 0 || (uint64_t)msg.value >= w->count) return (void *)1;
        uint64_t id = (uint64_t)msg.value;
        atomic_fetch_add_explicit(&w->seen[id], 1, memory_order_relaxed);
        atomic_fetch_add_explicit(w->sum, id, memory_order_relaxed);
        atomic_fetch_add_explicit(&consumed, 1, memory_order_relaxed);
        fr_msg_free_payload(&msg);
    }
}
static double seconds(struct timespec a, struct timespec b) { return (double)(b.tv_sec-a.tv_sec) + (double)(b.tv_nsec-a.tv_nsec)/1e9; }
static int run(uint64_t count, unsigned receivers) {
    fr_process_t *p = fr_process_create("mailbox-bench");
    if (!p) return 2;
    atomic_uint_fast64_t *seen = calloc((size_t)count, sizeof(*seen));
    pthread_t *threads = calloc(receivers, sizeof(*threads));
    worker_t *args = calloc(receivers, sizeof(*args));
    if (!seen || !threads || !args) return 2;
    atomic_uint_fast64_t sum = 0; atomic_store(&consumed, 0);
    for (unsigned i=0;i<receivers;i++) { args[i]=(worker_t){p,count,seen,&sum}; if (pthread_create(&threads[i],NULL,consumer,&args[i])) return 2; }
    struct timespec start,end; clock_gettime(CLOCK_MONOTONIC,&start);
    uint64_t sent=0;
    while (sent<count) { if (fr_send(p,1,(int64_t)sent,NULL,0)) sent++; else sched_yield(); }
    for (unsigned i=0;i<receivers;i++) while (!fr_send(p,0,0,NULL,0)) sched_yield();
    for (unsigned i=0;i<receivers;i++) { void *result=NULL; pthread_join(threads[i],&result); if (result) return 2; }
    clock_gettime(CLOCK_MONOTONIC,&end);
    uint64_t expected=(count*(count-1))/2, bad=0;
    for (uint64_t i=0;i<count;i++) if (atomic_load_explicit(&seen[i],memory_order_relaxed)!=1) bad++;
    double elapsed=seconds(start,end); uint64_t got=atomic_load(&consumed), actual=atomic_load(&sum);
    printf("runtime,receivers,messages,wall_s,msg_per_s,consumed,checksum,missing_or_duplicate\nForge,%u,%" PRIu64 ",%.6f,%.0f,%" PRIu64 ",%" PRIu64 ",%" PRIu64 "\n",receivers,count,elapsed,count/elapsed,got,actual,bad);
    fr_process_destroy(p); free(args); free(threads); free(seen);
    return got!=count || actual!=expected || bad!=0;
}
int main(int argc,char **argv) {
    if (argc!=3) return 2;
    char *e1,*e2; uint64_t count=strtoull(argv[1],&e1,10); unsigned long receivers=strtoul(argv[2],&e2,10);
    if (*e1 || *e2 || !count || count>10000000 || !receivers || receivers>64) return 2;
    return run(count,(unsigned)receivers);
}
