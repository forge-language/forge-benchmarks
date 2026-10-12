#!/usr/bin/env python3
"""Paired Forge-runtime vs Rust bounded-mailbox benchmark."""
import argparse, csv, os, pathlib, random, statistics, subprocess, time
ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent

def run_one(binary, runtime, count, receivers):
    text = subprocess.check_output([str(binary), str(count), str(receivers)], text=True)
    rows = list(csv.DictReader(text.splitlines()))
    if len(rows) != 1: raise RuntimeError(f"unexpected output from {binary}: {text}")
    row = rows[0]
    if int(row['consumed']) != count or int(row['missing_or_duplicate']) != 0:
        raise RuntimeError(f"message integrity check failed: {row}")
    if int(row['checksum']) != count * (count - 1) // 2:
        raise RuntimeError(f"checksum failed: {row}")
    return {'runtime': runtime, 'receivers': receivers, 'messages': count,
            'wall_s': float(row['wall_s']), 'msg_per_s': float(row['msg_per_s']),
            'consumed': int(row['consumed']), 'checksum': int(row['checksum']),
            'missing_or_duplicate': int(row['missing_or_duplicate'])}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--messages',type=int,default=1_000_000); ap.add_argument('--pairs',type=int,default=10); ap.add_argument('--receivers',type=int,nargs='+',default=[1,4,16]); ap.add_argument('--output',type=pathlib.Path)
    a=ap.parse_args(); runtime=pathlib.Path(os.environ.get('FORGE_RUNTIME_DIR', ROOT.parent/'forge-runtime')).resolve()
    binary=HERE/'target'/'mailbox_forge'
    binary.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['cc','-O3','-DNDEBUG',f'-I{runtime / "include"}',str(HERE/'mailbox_bench.c'),str(runtime/'build/lib/libforge_runtime.a'),'-pthread','-o',str(binary)],check=True)
    subprocess.run(['cargo','build','--release','--manifest-path',str(HERE/'Cargo.toml')],check=True)
    rust=HERE/'target'/'release'/'mailbox-bench'
    records=[]
    for receivers in a.receivers:
        for pair in range(a.pairs):
            order=['Forge','Rust'];
            if pair % 2: order.reverse()
            for name in order:
                binary_to_run=binary if name=='Forge' else rust
                row=run_one(binary_to_run,name,a.messages,receivers); row['pair']=pair+1
                records.append(row)
                print(f"{receivers} receivers pair {pair+1}/{a.pairs}: {name} {row['msg_per_s']:.0f} msg/s",flush=True)
    out=a.output or ROOT/'docs'/f'mailbox-forge-rust-{time.strftime("%Y-%m-%d",time.gmtime())}.csv'
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['receivers','pair','runtime','messages','wall_s','msg_per_s','consumed','checksum','missing_or_duplicate']);w.writeheader();w.writerows(records)
    print(f"\nreceivers | Forge median msg/s | Rust median msg/s | Forge/Rust paired throughput ratio (bootstrap 95% interval)")
    for receivers in a.receivers:
        subset=[r for r in records if r['receivers']==receivers]
        f=[r['msg_per_s'] for r in subset if r['runtime']=='Forge']; z=[r['msg_per_s'] for r in subset if r['runtime']=='Rust']
        paired=[]
        for pair in range(1,a.pairs+1):
            f1=next(r['msg_per_s'] for r in subset if r['pair']==pair and r['runtime']=='Forge')
            z1=next(r['msg_per_s'] for r in subset if r['pair']==pair and r['runtime']=='Rust')
            paired.append(f1/z1)
        rng=random.Random(124+receivers)
        boots=sorted(statistics.median(rng.choices(paired,k=len(paired))) for _ in range(30_000))
        low=boots[int(0.025*len(boots))]; high=boots[int(0.975*len(boots))-1]
        print(f"{receivers:9d} | {statistics.median(f):17,.0f} | {statistics.median(z):16,.0f} | {statistics.median(paired):.3f} [{low:.3f}, {high:.3f}]")
    print(f"Raw samples: {out}")
if __name__=='__main__': main()
