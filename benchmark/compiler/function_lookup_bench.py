"""Compare compiler lookup scaling, preserving emitted C/JS byte for byte."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import time


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def confidence(ratios):
    values = list(map(math.log, ratios))
    rng = random.Random(20261015)
    draws = sorted(math.exp(statistics.mean(rng.choices(values, k=len(values))))
                   for _ in range(10000))
    return [draws[249], draws[9749]]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'candidate', 'root', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--pairs', type=int, default=12)
    p.add_argument('--sizes', type=int, nargs='+', default=[16,17,1000,4000,16000])
    p.add_argument('--cpu', type=int)
    p.add_argument("--source-root", type=Path, required=True, help="Forge compiler source checkout")
    args = p.parse_args()
    if args.pairs < 2 or any(n < 1 for n in args.sizes):
        p.error('need at least two pairs and positive owner sizes')
    out, root = args.output.resolve(), args.root.resolve()
    out.mkdir(parents=True, exist_ok=False)
    if hasattr(os, 'sched_getaffinity'):
        available = sorted(os.sched_getaffinity(0))
        cpu = available[0] if args.cpu is None else args.cpu
        if cpu not in available:
            p.error(f'CPU {cpu} not available: {available}')
        os.sched_setaffinity(0, {cpu})
    elif args.cpu is not None:
        p.error('CPU affinity unsupported on this platform')
    else:
        cpu = None
    compilers = {}
    for label in ('baseline', 'candidate'):
        target = out/('forge-'+label)
        shutil.copy2(getattr(args, label).resolve(), target)
        compilers[label] = target
    repo = args.source_root.resolve()
    cases = []
    for name, original in [('hello',repo/'examples/hello.fg'), ('bootstrap',repo/'bootstrap/compiler.fg')]:
        source = out/(name+'.fg')
        shutil.copy2(original, source)
        cases.append((name+'_check', source, '--check'))
        if name == 'bootstrap':
            cases.append((name+'_emit_c', source, '--emit-c'))
    for n in args.sizes:
        text = ''.join(f'fn work_{i}(x:int):int{{return work_{(i+1)%n}(x);}}\n'
                       for i in range(n))
        source = out/f'top-{n}.fg'
        source.write_text(text+'native main{return 0;}')
        cases.append((f'top_{n}_check', source, '--check'))
        folder = out/f'module-{n}'
        folder.mkdir()
        (folder/'helpers.fg').write_text(text)
        source = folder/'main.fg'
        source.write_text('import helpers;native main{return 0;}')
        cases.append((f'module_{n}_emit_js', source, '--emit-js'))
    largest = max(args.sizes)
    cases += [(f'top_{largest}_emit_c', out/f'top-{largest}.fg', '--emit-c'),
              (f'module_{largest}_check', out/f'module-{largest}'/'main.fg', '--check')]
    literals = ''.join(f'fn value_{i}():int{{return {i};}}\n' for i in range(largest))
    for name, text in [('unused',literals+'native main{return 0;}'),
                       ('single',literals+f'native main{{return value_{largest-1}();}}'),
                       ('front', 'fn work_0(x:int):int{return x;}'+''.join(
                           f'fn work_{i}(x:int):int{{return work_0(x);}}\n'
                           for i in range(1,largest))+'native main{return 0;}')]:
        source = out/(name+'.fg')
        source.write_text(text)
        cases.append((f'{name}_{largest}_check', source, '--check'))
    report = {
        'schema': 1, 'platform': platform.platform(), 'python': platform.python_version(),
        'cpu': cpu, 'pairs': args.pairs, 'script_sha256': digest(__file__),
        'timing': 'perf_counter_ns around CLI subprocess, including startup',
        'interval': 'row-wise paired geometric mean, 10000 percentile bootstrap resamples',
        'compiler_sha256': {label: digest(path) for label, path in compilers.items()},
        'source_sha256': {str(path.relative_to(out)): digest(path) for path in out.rglob('*.fg')},
        'results': [],
    }
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.exists():
        report['cpu_model'] = next((line.split(':',1)[1].strip()
                                   for line in cpuinfo.read_text().splitlines()
                                   if line.startswith('model name')), 'unknown')
    for name, source, mode in cases:
        commands, samples, outputs = {}, [], {}
        for label in compilers:
            command = [str(compilers[label]), str(source), mode, '--forge-root', str(root)]
            if mode != '--check':
                outputs[label] = out/(name+'-'+label+('.c' if mode == '--emit-c' else '.js'))
                command += ['-o', str(outputs[label])]
            commands[label] = command
        for pair in range(-1, args.pairs):
            order = ['baseline','candidate'] if pair % 2 == 0 else ['candidate','baseline']
            sample = {'pair':pair, 'order':order}
            for label in order:
                start = time.perf_counter_ns()
                result = subprocess.run(commands[label], capture_output=True, text=True, timeout=60)
                sample[label] = (time.perf_counter_ns()-start)/1e9
                if result.returncode or result.stdout or result.stderr:
                    raise RuntimeError(f'{commands[label]}: {result.returncode}\n{result.stdout}\n{result.stderr}')
            if outputs and outputs['baseline'].read_bytes() != outputs['candidate'].read_bytes():
                raise RuntimeError(f'{name}: generated output changed')
            if pair >= 0:
                samples.append(sample)
        ratios = [row['baseline']/row['candidate'] for row in samples]
        row = {
            'case':name, 'mode':mode, 'commands':commands, 'samples':samples,
            'median_seconds': {label: statistics.median(s[label] for s in samples) for label in compilers},
            'paired_geomean_speedup': math.exp(statistics.mean(map(math.log, ratios))),
            'paired_bootstrap_95ci': confidence(ratios),
            'output_sha256': {label:digest(path) for label,path in outputs.items()},
        }
        report['results'].append(row)
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
        print(f"{name}: {row['paired_geomean_speedup']:.3f}x {row['paired_bootstrap_95ci']}", flush=True)


if __name__ == '__main__':
    main()
