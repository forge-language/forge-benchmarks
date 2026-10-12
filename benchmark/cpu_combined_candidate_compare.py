#!/usr/bin/env python3
"""Compare combined Forge LCG-fold and bounded Miller-Rabin kernels to controls."""
import argparse, itertools, json, os, random, statistics, sys, time
from pathlib import Path
from cpu_compare import confidence, reference, run_binary, sha

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-forge',type=Path,required=True)
    p.add_argument('--candidate-forge',type=Path,required=True)
    p.add_argument('--rust',type=Path,required=True)
    p.add_argument('--candidate-source',type=Path,required=True)
    p.add_argument('--baseline-report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pairs',type=int,default=48)
    p.add_argument('--workloads',nargs='+',choices=['lcg','primes','scan','builder','immutable'],default=['lcg','primes','scan','builder','immutable'])
    p.add_argument('--cpu',type=int,default=min(os.sched_getaffinity(0)))
    a=p.parse_args()
    if a.pairs<12 or a.pairs%6: p.error('--pairs must be a multiple of six and >=12')
    if a.cpu not in os.sched_getaffinity(0): p.error('CPU is outside affinity')
    binaries={'baseline_forge':a.baseline_forge,'candidate_forge':a.candidate_forge,'rust':a.rust}
    all_dims={'lcg':(250000,64),'primes':(2000,128),'scan':(131072,512),'builder':(32768,1024),'immutable':(4096,512)}
    dims={mode:all_dims[mode] for mode in a.workloads}
    rng=random.Random(20261014)
    checks=[]
    seeds=[-1000100,-1000001,-1000000,-999999,-1,0,1,17,719,100000]
    for mode,(n,rounds) in dims.items():
        cases=[(x,y,s) for x,y in [(0,5),(1,1),(2,1),(3,2),(31,4),(127,5)] for s in seeds]
        cases += [(rng.randint(0,40),rng.randint(1,4),rng.randint(-1000100,100000)) for _ in range(100)]
        cases += [(rng.randint(0,40),rng.randint(1,4),rng.choice(seeds)) for _ in range(40)]
        for x,y,s in cases:
            want=reference(mode,x,y,s)
            for label,binary in binaries.items():
                row=run_binary(binary,mode,x,y,s,a.cpu)
                if row['checksum']!=want: raise RuntimeError(f'{label} mismatch {mode}/{x}/{y}/{s}')
            checks.append({'workload':mode,'n':x,'rounds':y,'seed':s,'checksum':want})
    rows=[];prewarms=[];summaries={}
    started=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    for mode,(n,rounds) in dims.items():
        orders=list(itertools.permutations(binaries))* (a.pairs//6);rng.shuffle(orders)
        ratio_rows={'baseline_forge_over_candidate_forge':[], 'rust_over_candidate_forge':[], 'rust_over_baseline_forge':[]}
        for pair,order in enumerate(orders):
            seed=rng.randint(1,100000);want=reference(mode,n,rounds,seed);elapsed={}
            for pos,label in enumerate(order):
                warm=run_binary(binaries[label],mode,n,rounds,seed,a.cpu)
                if warm['checksum']!=want: raise RuntimeError('prewarm mismatch')
                prewarms.append({'workload':mode,'pair':pair,'order':pos,'implementation':label,'seed':seed,**warm})
                row=run_binary(binaries[label],mode,n,rounds,seed,a.cpu)
                if row['checksum']!=want: raise RuntimeError('measurement mismatch')
                elapsed[label]=row['kernel_ns'];rows.append({'workload':mode,'pair':pair,'order':pos,'implementation':label,'n':n,'rounds':rounds,'seed':seed,'checksum':want,**row})
            ratio_rows['baseline_forge_over_candidate_forge'].append(elapsed['baseline_forge']/elapsed['candidate_forge'])
            ratio_rows['rust_over_candidate_forge'].append(elapsed['rust']/elapsed['candidate_forge'])
            ratio_rows['rust_over_baseline_forge'].append(elapsed['rust']/elapsed['baseline_forge'])
        summaries[mode]={key:{'median':statistics.median(vals),'ci95':confidence(vals,20261014+j)} for j,(key,vals) in enumerate(ratio_rows.items())}
    report={'started_at_utc':started,'finished_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'method':{'pairs_per_workload':a.pairs,'cpu':a.cpu,'ordering':'randomized balanced all six permutations per workload','prewarming':'same input immediately before every measurement','scope':'combined source-level Forge algorithm candidates against unchanged Forge/Rust controls; not a compiler-wide claim','workloads':dims},'candidate':{'source':str(a.candidate_source),'source_sha256':sha(a.candidate_source),'binary_sha256':sha(a.candidate_forge),'baseline_binary_sha256':sha(a.baseline_forge),'rust_binary_sha256':sha(a.rust),'baseline_report':str(a.baseline_report),'baseline_report_sha256':sha(a.baseline_report)},'correctness_cases':checks,'prewarms':prewarms,'measurements':rows,'summary':summaries,'runner_source':Path(__file__).read_text(),'runner_sha256':sha(Path(__file__))}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summaries,indent=2));print(f"correctness={len(checks)} prewarms={len(prewarms)} measurements={len(rows)}");print('raw report: '+str(a.output))
if __name__=='__main__':main()
