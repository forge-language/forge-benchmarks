"""Paired CLI workloads for dynamic binding lookup; emitted C must be identical."""
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


def body(count, kind):
    result = 'let seed:int=7;'
    for i in range(count):
        value = 'seed' if kind == 'oldest' or (kind == 'newest' and i == 0) else f'v{i-1}'
        result += f'let v{i}:int=' + (str(i) if kind == 'literal' else value+'+1') + ';'
    return result + 'return 0;'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','candidate','root','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--pairs',type=int,default=24)
    p.add_argument('--cpu',type=int,default=2)
    p.add_argument("--source-root", type=Path, required=True, help="Forge compiler source checkout")
    args = p.parse_args()
    if args.pairs < 2:
        p.error('need at least two pairs')
    out, root = args.output.resolve(), args.root.resolve()
    out.mkdir(parents=True,exist_ok=False)
    if hasattr(os,'sched_setaffinity'):
        os.sched_setaffinity(0,{args.cpu})
    compilers = {}
    for label in ['baseline','candidate']:
        compilers[label] = out/('forge-'+label)
        shutil.copy2(getattr(args,label).resolve(),compilers[label])
    repo = args.source_root.resolve()
    cases = []
    for name, source in [('hello',repo/'examples/hello.fg'),('bootstrap',repo/'bootstrap/compiler.fg')]:
        target = out/(name+'.fg');shutil.copy2(source,target)
        cases.append((name+'_check',target,'--check'))
        if name == 'bootstrap': cases.append((name+'_emit_c',target,'--emit-c'))
    for n in [16,32,33,128,1024,8192]:
        for kind in (['oldest'] if n <= 33 else ['oldest','newest','literal']):
            source = out/(kind+'-'+str(n)+'.fg')
            source.write_text('fn work():int{'+body(n,kind)+'}native main{return 0;}')
            cases += [(f'{kind}_{n}_check',source,'--check'),
                      (f'{kind}_{n}_emit_c',source,'--emit-c')]
    mixed = out/'mixed.fg'
    mixed.write_text('fn big():int{'+body(8192,'oldest')+'}'+''.join(
        f'fn small_{i}():int{{'+body(48,'oldest')+'}' for i in range(128))+'native main{return 0;}')
    cases += [('mixed_check',mixed,'--check'),('mixed_emit_c',mixed,'--emit-c')]
    report = {'schema':1,'platform':platform.platform(),'cpu':args.cpu,'pairs':args.pairs,
              'compiler_sha256':{k:digest(v) for k,v in compilers.items()},
              'script_sha256':digest(__file__),
              'statistics_helper_sha256':digest(Path(__file__).with_name('function_lookup_bench.py')),
              'source_sha256':{x.name:digest(x) for x in out.glob('*.fg')},
              'timing':'perf_counter_ns around CLI subprocess, including process startup',
              'results':[]}
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.exists():
        report['cpu_model'] = next(line.split(':',1)[1].strip() for line in cpuinfo.read_text().splitlines() if line.startswith('model name'))
    for name, source, mode in cases:
        commands, outputs, samples = {}, {}, []
        for label in compilers:
            command = [str(compilers[label]),str(source),mode,'--forge-root',str(root)]
            if mode == '--emit-c':
                outputs[label] = out/(name+'-'+label+'.c')
                command += ['-o',str(outputs[label])]
            commands[label] = command
        for pair in range(-1,args.pairs):
            order = ['baseline','candidate'] if pair%2 == 0 else ['candidate','baseline']
            sample = {'pair':pair,'order':order}
            for label in order:
                start = time.perf_counter_ns()
                r = subprocess.run(commands[label],capture_output=True,text=True,timeout=60)
                sample[label] = (time.perf_counter_ns()-start)/1e9
                if r.returncode or r.stdout or r.stderr:
                    raise RuntimeError(f'{commands[label]}: {r.returncode}\n{r.stdout}\n{r.stderr}')
            if outputs and outputs['baseline'].read_bytes()!=outputs['candidate'].read_bytes():
                raise RuntimeError(name+': emitted C changed')
            if pair >= 0: samples.append(sample)
        ratios = [r['baseline']/r['candidate'] for r in samples]
        row = {'case':name,'commands':commands,'samples':samples,
               'median_seconds':{k:statistics.median(r[k] for r in samples) for k in compilers},
               'paired_geomean_speedup':math.exp(statistics.mean(map(math.log,ratios))),
               'paired_bootstrap_95ci':confidence(ratios),
               'output_sha256':{k:digest(v) for k,v in outputs.items()}}
        report['results'].append(row)
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(name,round(row['paired_geomean_speedup'],3),row['paired_bootstrap_95ci'],flush=True)


if __name__ == '__main__':main()
