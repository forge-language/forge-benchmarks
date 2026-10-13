"""Check generated-C screening kernels against independent wrapping oracles."""
import argparse
import os
from pathlib import Path
import random
import subprocess
import tempfile

from cross_os_cpu_compare import apply_probe, ROOT

MIN, MAX = -(1 << 63), (1 << 63) - 1


def wrap(value):
    return (value + (1 << 63)) % (1 << 64) - (1 << 63)


def remainder(value, divisor):
    if not divisor or (value == MIN and divisor == -1):
        raise ArithmeticError()
    quotient = abs(value) // abs(divisor) * (-1 if (value < 0) != (divisor < 0) else 1)
    return value - quotient * divisor


def power(base, exponent, modulus):
    result, factor = 1, remainder(base, modulus)
    while exponent > 0:
        if exponent % 2 == 1:
            result = remainder(wrap(result * factor), modulus)
        factor = remainder(wrap(factor * factor), modulus)
        exponent //= 2
    return result


def mr(value, base):
    if base >= value:
        return 1
    d, s = wrap(value - 1), 0
    if not d:
        raise ValueError('Exclude the original nonterminating d=0 case')
    while remainder(d, 2) == 0:
        d = (abs(d) // 2) * (-1 if d < 0 else 1)
        s += 1
    x = power(base, d, value)
    if x == 1 or x == wrap(value - 1):
        return 1
    for _ in range(1, s):
        x = remainder(wrap(x * x), value)
        if x == wrap(value - 1):
            return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generated-c', type=Path, required=True)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--probe', choices=['range-kernels','hybrid-range','precision-range','target-remainder','tight-pow'], default='range-kernels')
    parser.add_argument('--extra-c-flag', action='append', default=[])
    args = parser.parse_args()
    original = args.generated_c.read_text()
    candidate, _ = apply_probe(original, args.probe)
    driver = '''
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    int64_t a=strtoll(argv[2],NULL,10), b=strtoll(argv[3],NULL,10), c=strtoll(argv[4],NULL,10);
    int64_t result;
    if (!strcmp(argv[1],"lcg")) result=lcg(a,b,c);
    else if (!strcmp(argv[1],"pow")) result=prime_mod_pow(a,b,c);
    else if (!strcmp(argv[1],"mr")) result=prime_mr_pass(a,b);
    else if (!strcmp(argv[1],"weighted")) {
        size_t count = a > 0 ? (size_t)a : 0;
        char *data = malloc(count+1);
        if (!data) return 2;
        for (size_t i=0;i<count;i++) data[i]=(char)(1+(((uint64_t)i+(uint64_t)b)%255));
        data[count]=0;
        result=weighted(fr_str_view(data),c);
        free(data);
    }
    else return 2;
    printf("%lld\\n",(long long)result); return 0;
}
'''
    rng = random.Random(20261013)
    cases = []
    for seed in (MIN, MIN+1, -2147483647, -1, 0, 1, 2147483646, 2147483647, MAX):
        for n, rounds in ((-1,3),(0,3),(1,1),(13,3),(31,7),(13,-1)):
            value = seed
            for _ in range(max(rounds, 0)):
                for _ in range(max(n, 0)):
                    value = remainder(wrap(value * 48271), 2147483647)
            cases.append(('lcg',(n,rounds,seed),value))
    bounds = (MIN,-26,-1,1,2,3,26,65537,1000003,1373651,
              2097151,2097152,2097153,3037000498,3037000499,3037000500,MAX)
    for modulus in bounds:
        for base, exponent in ((MIN,-1),(-1,3),(0,0),(1,MAX),(MAX,0),(MAX,63),(modulus-1 if modulus>0 else 3,31)):
            try: expected = power(base,exponent,modulus)
            except ArithmeticError: expected = None
            cases.append(('pow',(base,exponent,modulus),expected))
    for _ in range(100):
        base=rng.randrange(MIN,MAX+1);exponent=rng.randrange(-1,128);modulus=rng.choice(bounds)
        try: expected = power(base,exponent,modulus)
        except ArithmeticError: expected = None
        cases.append(('pow',(base,exponent,modulus),expected))
    for value in (MIN,-3,-1,0,2,3,4,5,13,1373651,3037000499,3037000500,MAX):
        for base in (MIN,-1,0,2,3,MAX):
            try: expected = mr(value,base)
            except ArithmeticError: expected = None
            cases.append(('mr',(value,base,0),expected))
    for base, exponent, modulus in ((1,0,0),(MIN,1,-1)):
        cases.append(('pow',(base,exponent,modulus),None))
    for n in (0,1,12,13,14,25,26,27,128):
        for seed in (MIN,-1,0,MAX):
            for offset in (MIN,-26,-13,-12,-1,0,1,12,13,MAX):
                weight=remainder(offset,13)+1;result=0
                for i in range(n):
                    byte=1+(((i+seed)&((1<<64)-1))%255)
                    result=wrap(result+byte*weight)
                    weight+=1
                    if weight>13:weight=1
                cases.append(('weighted',(n,seed,offset),result))
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        for name, source in (('original',original),('candidate',candidate)):
            if source.count('\nint main(') != 1:
                raise RuntimeError('Unexpected generated main shape')
            c=work/(name+'.c');c.write_text(source.replace('\nint main(','\nint fixture_main(',1)+driver)
            for opt in ('-O0','-O3'):
                binary=work/(name+opt+('.exe' if os.name=='nt' else ''))
                link=['-lws2_32','-lkernel32','-lm'] if os.name=='nt' else ['-lpthread','-lm']
                subprocess.run([args.cc,'-std=gnu11',opt,'-fsanitize=undefined','-fno-sanitize-recover=all',
                                *args.extra_c_flag,
                                '-I',str(args.sdk/'include'),str(c),str(ROOT/'benchmark/cpu/clock_portable.c'),
                                '-L',str(args.sdk/'lib'),'-lforge_std','-lforge_runtime',*link,'-o',str(binary)],
                               check=True,capture_output=True,text=True,timeout=60)
                for mode, inputs, expected in cases:
                    result=subprocess.run([str(binary),mode,*map(str,inputs)],capture_output=True,text=True,timeout=5)
                    if expected is None:
                        assert result.returncode==1 and result.stderr=='Forge integer division\n', (name,opt,mode,inputs,result)
                    else:
                        assert result.returncode==0 and result.stderr=='' and result.stdout==str(expected)+'\n', (name,opt,mode,inputs,expected,result)
                print(name,opt,len(cases),'oracle and trap cases passed')


if __name__ == '__main__':
    main()
