/* Diagnostic-only companion to dispatch_bench.c. Never use its timings. */
#include "forge_runtime.h"
#include "forge/thread.h"
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
static fr_mutex_t *owner, *queues[256];
static int queue_count;
static _Thread_local int constructing;
static atomic_size_t private_acquires, owner_acquires;
fr_mutex_t *__real_fr_mutex_create(void);
fr_mutex_t *__wrap_fr_mutex_create(void) {
    fr_mutex_t *m=__real_fr_mutex_create();
    if(constructing&&m) {
        if(!owner)owner=m;
        else {if(queue_count==256)abort();queues[queue_count++]=m;}
    }
    return m;
}
static void report(void) {
    fprintf(stderr,"queue-lock-probe: registered=%d private=%zu owner=%zu\n",
            queue_count,atomic_load(&private_acquires),atomic_load(&owner_acquires));
}
fr_scheduler_t *__real_fr_scheduler_create(int);
fr_scheduler_t *__wrap_fr_scheduler_create(int workers) {
    if(owner)abort();
    constructing=1;
    fr_scheduler_t *s=__real_fr_scheduler_create(workers);constructing=0;
    if(!s||queue_count!=2*fr_scheduler_worker_count(s))abort();
    atexit(report);return s;
}
void __real_fr_mutex_lock(fr_mutex_t *);
void __wrap_fr_mutex_lock(fr_mutex_t *m) {
    if(m&&m==owner)atomic_fetch_add(&owner_acquires,1);
    for(int i=0;i<queue_count;i++)if(m&&queues[i]==m)atomic_fetch_add(&private_acquires,1);
    __real_fr_mutex_lock(m);
}
