"""Paired constant-name lookup workloads; C/JS output must remain identical."""
import argparse
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import time
from function_lookup_bench import confidence, digest


def source(count, shape):
    constants = ''.join(f'const K_{i:05d}={i};\n' for i in range(count))
    def value(i):
        if shape in ('unused', 'single'): return str(i)
        if shape == 'first': return 'K_00000'
        if shape == 'spread': return f'K_{(i*71)%count:05d}'
        return f'K_{count-1:05d}'
    functions = ''.join(f'fn value_{i}():int{{return {value(i)};}}\n' for i in range(count))
    result = f'K_{count-1:05d}' if shape == 'single' else '0'
    return constants + functions + f'native main{{return {result};}}'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','candidate','root','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--pairs',type=int,default=24)
    p.add_argument('--cpu',type=int,default=2)
    p.add_argument("--source-root", type=Path, required=True, help="Forge compiler source checkout")
    args = p.parse_args()
    if args.pairs < 2: p.error('need at least two pairs')
    out, root = args.output.resolve(), args.root.resolve()
    out.mkdir(parents=True,exist_ok=False)
    if hasattr(os,'sched_setaffinity'): os.sched_setaffinity(0,{args.cpu})
    compilers={}
    for label in ['baseline','candidate']:
        compilers[label]=out/('forge-'+label)
        shutil.copy2(getattr(args,label).resolve(),compilers[label])
    repo=args.source_root.resolve()
    cases=[]
    for name,path in [('hello',repo/'examples/hello.fg'),('bootstrap',repo/'bootstrap/compiler.fg')]:
        target=out/(name+'.fg');shutil.copy2(path,target)
        cases.append((name+'_check',target,'--check'))
        if name=='bootstrap':cases.append((name+'_emit_c',target,'--emit-c'))
    for n in [16,17,128,1024,8192,16384]:
        for shape in (['last'] if n<8192 else ['last','first','spread','unused','single']):
            path=out/f'{shape}-{n}.fg';path.write_text(source(n,shape))
            cases.append((f'{shape}_{n}_check',path,'--check'))
            if shape=='last' and n in [17,16384]:
                cases.extend((f'{shape}_{n}_{mode[2:].replace("-","_")}',path,mode)
                             for mode in ['--emit-c','--emit-js'])
    folder=out/'imported';folder.mkdir()
    (folder/'helper.fg').write_text(source(8192,'last').split('native main')[0])
    path=folder/'main.fg';path.write_text('import helper;native main{return 0;}')
    cases += [('imported_8192_check',path,'--check'),('imported_8192_emit_js',path,'--emit-js')]
    report={'schema':1,'platform':platform.platform(),'cpu':args.cpu,'pairs':args.pairs,
            'compiler_sha256':{k:digest(v) for k,v in compilers.items()},
            'script_sha256':digest(__file__),
            'statistics_helper_sha256':digest(Path(__file__).with_name('function_lookup_bench.py')),
            'source_sha256':{str(x.relative_to(out)):digest(x) for x in out.rglob('*.fg')},
            'timing':'perf_counter_ns around CLI subprocess, including startup',
            'interval':'row-wise paired geometric mean, 10000 percentile bootstrap resamples',
            'results':[]}
    cpuinfo=Path('/proc/cpuinfo')
    if cpuinfo.exists():report['cpu_model']=next(line.split(':',1)[1].strip() for line in cpuinfo.read_text().splitlines() if line.startswith('model name'))
    for name,path,mode in cases:
        commands={};outputs={};samples=[]
        for label in compilers:
            commands[label]=[str(compilers[label]),str(path),mode,'--forge-root',str(root)]
            if mode!='--check':
                outputs[label]=out/(name+'-'+label+('.c' if mode=='--emit-c' else '.js'))
                commands[label]+=['-o',str(outputs[label])]
        for pair in range(-1,args.pairs):
            order=['baseline','candidate'] if pair%2==0 else ['candidate','baseline']
            sample={'pair':pair,'order':order}
            for label in order:
                start=time.perf_counter_ns();r=subprocess.run(commands[label],capture_output=True,text=True,timeout=60)
                sample[label]=(time.perf_counter_ns()-start)/1e9
                if r.returncode or r.stdout or r.stderr:raise RuntimeError(f'{commands[label]}: {r.returncode}\n{r.stdout}\n{r.stderr}')
            if outputs and outputs['baseline'].read_bytes()!=outputs['candidate'].read_bytes():raise RuntimeError(name+': emitted output changed')
            if pair>=0:samples.append(sample)
        ratios=[s['baseline']/s['candidate'] for s in samples]
        row={'case':name,'commands':commands,'samples':samples,
             'median_seconds':{k:statistics.median(s[k] for s in samples) for k in compilers},
             'paired_geomean_speedup':math.exp(statistics.mean(map(math.log,ratios))),
             'paired_bootstrap_95ci':confidence(ratios),
             'output_sha256':{k:digest(v) for k,v in outputs.items()}}
        report['results'].append(row)
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(name,round(row['paired_geomean_speedup'],3),row['paired_bootstrap_95ci'],flush=True)


if __name__=='__main__':main()
