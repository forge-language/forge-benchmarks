"""Paired codegen benchmark; validates checksums against a wrapping Python oracle.

Example: python3 ../forge-benchmarks/benchmark/compiler/modular_power_bench.py --baseline /tmp/forge-before \
  --candidate build/bin/forge --root build --output build/modpow-bench
Both compilers emit unmodified C for the same exported Forge function. Separate
translation units prevent constant propagation from the C measurement driver.
"""
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


SOURCE = '''library powers {
export fn residue(a:int,bits:int,d:int):int {
 let r:int=1;let x:int=a%d;let k:int=bits;
 while(k>0){if(k%2==1){r=(r*x)%d;}x=(x*x)%d;k=k/2;}return r;
}
}
'''
MAX = (1 << 63)-1


def oracle(a, exponent, d):
    def remainder(n):
        return n % d if n >= 0 else -((-n) % d)

    def product(a, b):
        n = (a*b + (1 << 63)) % (1 << 64) - (1 << 63)
        return remainder(n)

    result, factor = 1, remainder(a)
    while exponent > 0:
        if exponent & 1:
            result = product(result, factor)
        factor = product(factor, factor)
        exponent >>= 1
    return result


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, commands):
    command = [str(part) for part in command]
    commands.append(command)
    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError(f'{command!r}\n{result.stdout}\n{result.stderr}')
    return result.stdout


def interval(ratios):
    # Resample paired log speed ratios, preserving each AB/BA pair.
    logs = [math.log(value) for value in ratios]
    rng = random.Random(20261015)
    resampled = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs))))
                       for _ in range(10000))
    return [resampled[249], resampled[9749]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'candidate', 'root', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--pairs', type=int, default=12)
    parser.add_argument('--rounds', type=int, default=16384)
    parser.add_argument('--cpu', type=int)
    args = parser.parse_args()
    if args.pairs < 2 or args.rounds < 1:
        parser.error('at least two pairs and one round are required')
    root, output = args.root.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    cpu = args.cpu
    if hasattr(os, 'sched_getaffinity'):
        available = sorted(os.sched_getaffinity(0))
        cpu = min(available) if cpu is None else cpu
        if cpu not in available:
            parser.error(f'CPU {cpu} is outside affinity {available}')
        os.sched_setaffinity(0, {cpu})
    elif cpu is not None:
        parser.error('CPU affinity is unsupported on this platform')
    commands = []
    report = {
        'schema': 1, 'source': SOURCE, 'script_sha256': sha(__file__),
        'platform': platform.platform(), 'machine': platform.machine(),
        'python': platform.python_version(), 'cpu': cpu,
        'cc': run([args.cc, '--version'], commands).splitlines()[0],
        'rounds': args.rounds, 'pairs': args.pairs,
        'timing': 'perf_counter_ns around subprocess; includes process startup',
        'interval': '95% percentile bootstrap of paired geometric mean speed ratios; 10000 resamples',
        'sdk_sha256': {name: sha(root/name) for name in
                       ('lib/libforge_std.a', 'lib/libforge_runtime.a')},
        'sdk_headers_sha256': {str(path.relative_to(root)): sha(path)
                               for path in sorted((root/'include').rglob('*.h'))},
        'compilers': {}, 'results': [], 'commands': commands,
    }
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.exists():
        report['cpu_model'] = next((line.split(':', 1)[1].strip()
                                   for line in cpuinfo.read_text().splitlines()
                                   if line.startswith('model name')), 'unknown')
    for label in ('baseline', 'candidate'):
        work = output/label
        work.mkdir()
        compiler = getattr(args, label).resolve()
        shutil.copy2(compiler, work/'forge')
        (work/'power.fg').write_text(SOURCE)
        run([work/'forge', work/'power.fg', '--lib', '--emit-c',
             '--header', work/'powers.h', '-o', work/'power.c',
             '--forge-root', root], commands)
        run([args.cc, '-std=c11', '-O3', '-I', root/'include', '-c',
             work/'power.c', '-o', work/'power.o'], commands)
        report['compilers'][label] = {
            'path': str(compiler), 'sha256': sha(work/'forge'),
            'generated_c_sha256': sha(work/'power.c'),
        }

    groups = {
        'small_existing': ((3,26,65537,1000003,1373651,2097152), False),
        'power2_small': ((2,65536,1 << 21), False),
        'power2_small_negative': ((2,65536,1 << 21), True),
        'large_odd_fallback': ((998244353,1000000007,3037000499), False),
        'power2_bounded': ((1 << 22,1 << 24,1 << 30,1 << 31), False),
        'power2_wrapping': ((1 << 32,1 << 40,1 << 62), False),
        'power2_negative': ((1 << 22,1 << 31,1 << 40,1 << 62), True),
        'wrapping_fallback': ((3037000501,MAX), False),
    }
    rng = random.Random(20261015)
    for group, (divisors, negative) in groups.items():
        cases = [(-rng.randrange(1,MAX+1) if negative else rng.randrange(MAX+1),
                  rng.getrandbits(31) | 1,
                  divisors[i % len(divisors)]) for i in range(64)]
        expected = str((sum(oracle(*case) for case in cases)*args.rounds) % (1 << 64))
        records = ',\n'.join('{'+','.join(f'INT64_C({n})' for n in case)+'}'
                              for case in cases)
        driver = '''#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
extern int64_t frlib_powers_residue(int64_t, int64_t, int64_t);
static const int64_t inputs[][3] = {''' + records + '''};
int main(int argc, char **argv) {
 if (argc != 2) return 2;
 uint64_t checksum=0;
 unsigned long rounds=strtoul(argv[1],NULL,10);
 for (unsigned long i=0;i<rounds;i++)
  for (unsigned j=0;j<64;j++)
   checksum+=(uint64_t)frlib_powers_residue(inputs[j][0],inputs[j][1],inputs[j][2]);
 printf("%" PRIu64 "\\n",checksum);
 return 0;
}
'''
        path = output/(group+'.c')
        path.write_text(driver)
        binaries = {}
        for label in ('baseline', 'candidate'):
            binary = output/label/group
            run([args.cc, '-std=c11', '-O3', '-I', root/'include', path,
                 output/label/'power.o', '-L', root/'lib', '-lforge_std',
                 '-lforge_runtime', '-pthread', '-lm', '-o', binary], commands)
            binaries[label] = binary
        samples = []
        for pair in range(-1, args.pairs):  # One unrecorded warmup per executable.
            order = ('baseline', 'candidate') if pair % 2 == 0 else ('candidate', 'baseline')
            sample = {'pair': pair, 'order': list(order)}
            for label in order:
                start = time.perf_counter_ns()
                checksum = run([binaries[label], args.rounds], commands).strip()
                seconds = (time.perf_counter_ns()-start)/1e9
                if checksum != expected:
                    raise RuntimeError(f'{group} {label}: {checksum} != oracle {expected}')
                sample[label] = seconds
            if pair >= 0:
                samples.append(sample)
        ratios = [s['baseline']/s['candidate'] for s in samples]
        result = {
            'group': group, 'cases': cases, 'checksum': expected, 'samples': samples,
            'baseline_median_s': statistics.median(s['baseline'] for s in samples),
            'candidate_median_s': statistics.median(s['candidate'] for s in samples),
            'paired_geomean_speedup': math.exp(statistics.mean(map(math.log, ratios))),
            'paired_bootstrap_95ci': interval(ratios),
            'binary_sha256': {label: sha(binary) for label, binary in binaries.items()},
        }
        report['results'].append(result)
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
        print(f"{group}: {result['paired_geomean_speedup']:.3f}x "
              f"95% CI {result['paired_bootstrap_95ci']}", flush=True)


if __name__ == '__main__':
    main()
