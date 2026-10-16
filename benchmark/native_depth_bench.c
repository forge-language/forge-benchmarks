#define _GNU_SOURCE
#include "forge_runtime.h"
#include "forge/thread.h"
#include <stdatomic.h>
#include <sched.h>
#include <dirent.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
static uint64_t now_ns(clockid_t clock) {struct timespec t;clock_gettime(clock,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void record_affinity(void) {
 DIR *d=opendir("/proc/self/task");if(!d)return;struct dirent *entry;
 while((entry=readdir(d))) {char *end;long tid=strtol(entry->d_name,&end,10);if(*end||tid<=0)continue;
  cpu_set_t mask;if(sched_getaffinity((pid_t)tid,sizeof(mask),&mask))continue;
  fprintf(stderr,"affinity:%ld=",tid);for(int i=0;i<CPU_SETSIZE;i++)if(CPU_ISSET(i,&mask))fprintf(stderr,"%d,",i);fputc('\n',stderr);
 }closedir(d);
}
static atomic_size_t done;
typedef struct {uint64_t input,result,submitted,latency;unsigned steps;int timed;} item_t;
typedef struct {_Alignas(64) uint64_t jobs;} worker_stat_t;
static worker_stat_t worker_stats[128];
static atomic_uint next_slot;
static _Thread_local unsigned slot=128;
static int compare_latency(const void *a,const void *b){uint64_t x=*(const uint64_t*)a,y=*(const uint64_t*)b;return(x>y)-(x<y);}
static uint64_t expected(uint64_t x,unsigned steps){for(unsigned i=0;i<steps;i++)x=x*UINT64_C(6364136223846793005)+UINT64_C(1442695040888963407);return x;}
static void job(void *arg){
 if(slot==128){slot=atomic_fetch_add(&next_slot,1);if(slot>=128)exit(15);}
 item_t *p=arg;p->result=expected(p->input,p->steps);
 if(p->timed){p->latency=now_ns(CLOCK_MONOTONIC)-p->submitted;worker_stats[slot].jobs++;}
 atomic_fetch_add_explicit(&done,1,memory_order_release);
}
static void noop(void *arg){(void)arg;}
int main(int argc,char **argv){
 if(argc!=6)return 2;
 const char *mode=argv[1];int workers=atoi(argv[2]);size_t count=strtoull(argv[3],NULL,10);unsigned steps=(unsigned)strtoul(argv[4],NULL,10);uint64_t seed=strtoull(argv[5],NULL,10);
 if(workers<1||workers>128||count<1||count>10000000)return 3;
 fr_scheduler_t *s=fr_scheduler_create(workers);if(!s)return 4;
 uint64_t sum=0,wall,cpu,p50=0,p95=0,p99=0;int active=!strcmp(mode,"queried")||!strcmp(mode,"control");
 if(!strcmp(mode,"query")){
  for(unsigned i=0;i<steps;i++)if(fr_sched_pool_submit(s,noop,NULL))return 5;
  record_affinity();
  wall=now_ns(CLOCK_MONOTONIC);cpu=now_ns(CLOCK_PROCESS_CPUTIME_ID);
  for(size_t i=0;i<count;i++)sum+=fr_sched_pool_queued(s);
  cpu=now_ns(CLOCK_PROCESS_CPUTIME_ID)-cpu;wall=now_ns(CLOCK_MONOTONIC)-wall;
  if(sum!=(uint64_t)count*steps)return 6;
 }else{
  int queried=!strcmp(mode,"queried");if(!queried&&strcmp(mode,"control"))return 7;
  item_t *items=calloc(count,sizeof(*items));if(!items)return 8;
  for(size_t i=0;i<count;i++)items[i]=(item_t){.input=seed+(uint64_t)i,.steps=steps,.timed=1};
  /* Explicit fixture affinity isolates workers from the producer equally for
   * A/B. Verify masks rather than assuming a runtime helper imposes placement. */
  static const int worker_cpu[]={0,2,4,6,8,1,3,5,7,9};
  cpu_set_t mask;CPU_ZERO(&mask);
  for(int i=0;i<workers&&i<10;i++)CPU_SET(worker_cpu[i],&mask);
  if(sched_setaffinity(0,sizeof(mask),&mask))return 13;
  fr_scheduler_start(s);
  CPU_ZERO(&mask);CPU_SET(10,&mask);
  if(sched_setaffinity(0,sizeof(mask),&mask))return 14;
  item_t warm[64];for(unsigned i=0;i<64;i++){warm[i]=(item_t){.input=i,.steps=1};if(fr_sched_pool_submit(s,job,&warm[i]))return 9;}
  while(atomic_load_explicit(&done,memory_order_acquire)!=64)fr_thread_yield();
  atomic_store(&done,0);
  record_affinity();
  wall=now_ns(CLOCK_MONOTONIC);cpu=now_ns(CLOCK_PROCESS_CPUTIME_ID);
  size_t polls=0;
#ifdef FORGE_DEPTH_SINGLE_QUERY
  /* Diagnostic variant: one observation, then jobs without further queries. */
  if(!queried){polls++;if(fr_sched_pool_queued(s)!=0)return 18;}
#endif
  for(size_t i=0;i<count;i++){
   if(queried){for(;;){polls++;if(fr_sched_pool_queued(s)<2048)break;fr_thread_yield();}}
   items[i].submitted=now_ns(CLOCK_MONOTONIC);
   if(fr_sched_pool_submit(s,job,&items[i]))return 10;
  }
  while(atomic_load_explicit(&done,memory_order_acquire)!=count)fr_thread_yield();
  fr_scheduler_stop(s);
  cpu=now_ns(CLOCK_PROCESS_CPUTIME_ID)-cpu;wall=now_ns(CLOCK_MONOTONIC)-wall;
  for(size_t i=0;i<count;i++){if(items[i].result!=expected(items[i].input,steps))return 11;sum+=items[i].result;}
  if(fr_sched_pool_queued(s)!=0)return 12;
  uint64_t *latencies=malloc(count*sizeof(*latencies));if(!latencies)return 16;
  for(size_t i=0;i<count;i++)latencies[i]=items[i].latency;
  qsort(latencies,count,sizeof(*latencies),compare_latency);
  p50=latencies[count/2];p95=latencies[count*95/100];p99=latencies[count*99/100];free(latencies);
  uint64_t completed=0;for(int i=0;i<workers;i++)completed+=worker_stats[i].jobs;if(completed!=count)return 17;
  free(items);
  fprintf(stderr,"polls=%zu\n",polls);
 }
 fr_scheduler_destroy(s);
 printf("{\"mode\":\"%s\",\"workers\":%d,\"count\":%zu,\"steps\":%u,\"seed\":%llu,\"wall_ns\":%llu,\"cpu_ns\":%llu,\"checksum\":%llu,\"p50_ns\":%llu,\"p95_ns\":%llu,\"p99_ns\":%llu,\"per_worker_jobs\":[",mode,workers,count,steps,(unsigned long long)seed,(unsigned long long)wall,(unsigned long long)cpu,(unsigned long long)sum,(unsigned long long)p50,(unsigned long long)p95,(unsigned long long)p99);
 if(active)for(int i=0;i<workers;i++)printf("%s%llu",i?",":"",(unsigned long long)worker_stats[i].jobs);
 puts("]}");
 return 0;
}
