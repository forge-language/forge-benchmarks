#!/usr/bin/env python3
"""Paired exact-depth query and native-work comparisons on a controlled Linux CPU map."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def confidence(ratios):
    logs=list(map(math.log,ratios));rng=random.Random(20261015)
    boot=sorted(math.exp(statistics.mean(rng.choices(logs,k=len(logs)))) for _ in range(10000))
    return [boot[249],boot[9749]]


def reference(mode,count,steps,seed):
    if mode=='query':return count*steps
    # Independent affine exponentiation, rather than the callback's LCG loop.
    mask=(1<<64)-1;factor,offset=1,0;a,b=6364136223846793005,1442695040888963407
    while steps:
        if steps&1:factor,offset=factor*a&mask,(offset*a+b)&mask
        b=b*(a+1)&mask;a=a*a&mask;steps>>=1
    return (factor*(count*seed+count*(count-1)//2)+offset*count)&mask


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','candidate','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--pairs',type=int,default=24)
    args=p.parse_args()
    if args.pairs<2:p.error('need at least two pairs')
    if not hasattr(os,'sched_setaffinity') or not set(range(11))<=os.sched_getaffinity(0):p.error('fixture requires Linux CPUs 0..10; adapt both fixtures for another host')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    binaries={k:getattr(args,k).resolve() for k in ['baseline','candidate']}
    available=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{10})
    cases=[('query',w,200000,depth) for w in [1,2,4,12,64] for depth in [0,2048]]
    cases += [(mode,w,20000,16) for w in [1,2,4,8] for mode in ['queried','control']]
    cases += [(mode,4,20000,1024) for mode in ['queried','control']]
    report={'schema':1,'platform':platform.platform(),'available_cpus':available,'producer_cpu':10,
            'worker_cpu_order':[0,2,4,6,8,1,3,5,7,9],'pairs':args.pairs,
            'binary_sha256':{k:sha(v) for k,v in binaries.items()},'script_sha256':sha(__file__),
            'method':'Alternating AB/BA pairs; one excluded warmup pair; callbacks individually verified and checksum checked by Python affine oracle. Kernel wall/process CPU includes submit, completion, stop/join, excludes creation/warmup/verification. Query timing excludes queue construction/destruction.',
            'results':[]}
    def invoke(label,mode,workers,count,steps,seed):
        command=[str(binaries[label]),mode,str(workers),str(count),str(steps),str(seed)]
        proc=subprocess.run(command,capture_output=True,text=True,timeout=30,check=True)
        row=json.loads(proc.stdout);assert row['checksum']==reference(mode,count,steps,seed),row
        masks=[tuple(int(cpu) for cpu in line.split('=',1)[1].split(',') if cpu) for line in proc.stderr.splitlines() if line.startswith('affinity:')]
        expected=tuple(sorted(report['worker_cpu_order'][:workers]))
        assert masks.count((10,))==1,masks
        if mode=='query':assert len(masks)==1,masks
        else:
            assert len(masks)==workers+1 and masks.count(expected)==workers,masks
            assert sum(row['per_worker_jobs'])==count,row
        row.update(command=command,stderr=proc.stderr,observed_cpu_masks=[list(x) for x in masks])
        return row
    for mode,workers,count,steps in cases:
        samples=[]
        for pair in range(-1,args.pairs):
            seed=71+(pair+1)*719
            order=['baseline','candidate'] if pair%2==0 else ['candidate','baseline']
            sample={'pair':pair,'order':order}
            for label in order:sample[label]=invoke(label,mode,workers,count,steps,seed)
            if pair>=0:samples.append(sample)
        ratios=[x['baseline']['wall_ns']/x['candidate']['wall_ns'] for x in samples]
        summary={'mode':mode,'workers':workers,'count':count,'steps':steps,'samples':samples,
                 'paired_geomean_speedup':math.exp(statistics.mean(map(math.log,ratios))),
                 'paired_bootstrap_95ci':confidence(ratios),'medians':{}}
        for label in binaries:
            summary['medians'][label]={key:statistics.median(x[label][key] for x in samples) for key in ['wall_ns','cpu_ns','p50_ns','p95_ns','p99_ns']}
            if mode!='query':summary['medians'][label]['active_workers']=statistics.median(sum(n>0 for n in x[label]['per_worker_jobs']) for x in samples)
        report['results'].append(summary)
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(mode,workers,steps,round(summary['paired_geomean_speedup'],3),summary['paired_bootstrap_95ci'],flush=True)


if __name__=='__main__':main()
