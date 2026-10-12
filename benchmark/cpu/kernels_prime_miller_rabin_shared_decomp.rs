use std::env;
unsafe extern "C" { fn bench_clock_ns() -> i64; fn bench_observe_i64(value:i64)->i64; }
fn lcg(n:i64,rounds:i64,seed:i64)->i64 {
 let mut value=seed;let mut r=0;
 while r<rounds {let mut i=0;while i<n {value=(value*48271)%2147483647;i+=1;}r+=1;}value
}
fn prime_mod_pow(base:i64,exponent:i64,modulus:i64)->i64 {
 let mut result=1;let mut factor=base%modulus;let mut power=exponent;
 while power>0 {if power%2==1 {result=(result*factor)%modulus;}factor=(factor*factor)%modulus;power/=2;}result
}
fn prime_mr_pass(value:i64,base:i64,mut d:i64,s:i64)->bool {
 if base>=value {return true;}
 let mut x=prime_mod_pow(base,d,value);
 if x==1||x==value-1 {return true;}
 let mut r=1;while r<s {x=(x*x)%value;if x==value-1 {return true;}r+=1;}false
}
fn prime_is(value:i64)->bool {
 if value<2 {return false;}if value==2||value==3 {return true;}if value%2==0 {return false;}
 if value<1373653 {let mut d=value-1;let mut s=0;while d%2==0 {d/=2;s+=1;}return prime_mr_pass(value,2,d,s)&&prime_mr_pass(value,3,d,s);}
 let mut d=3;while d<=value/d {if value%d==0 {return false;}d+=2;}true
}
fn primes(n:i64,rounds:i64,seed:i64)->i64 {
 let mut sum=0;let mut r=0;
 while r<rounds {let mut i=0;while i<n {let value=1000001+seed+r*n+i;
  if prime_is(value) {sum+=value;}i+=1;}r+=1;}sum
}
fn pattern(n:i64,seed:i64)->String {
 let mut builder=String::with_capacity(n.max(0) as usize);let mut i=0;
 while i<n {builder.push((65+(i+seed)%26) as u8 as char);i+=1;}
 builder
}
fn weighted(bytes:&[u8],offset:i64)->i64 {
 let n=bytes.len() as i64;let mut i=0;let mut sum=0;let mut weight=offset%13+1;
 while i<n {sum+=bytes[i as usize] as i64*weight;i+=1;weight+=1;if weight>13 {weight=1;}}sum
}
fn scan(bytes:&[u8],rounds:i64,seed:i64)->i64 {
 let mut sum=seed;let mut r=0;while r<rounds {sum+=weighted(bytes,sum%13);r+=1;}sum
}
fn builder(n:i64,rounds:i64,seed:i64)->i64 {
 let mut sum=0;let mut r=0;
 while r<rounds {let text=pattern(n,seed+r);assert_eq!(text.len(),n as usize);sum+=weighted(text.as_bytes(),r%13);r+=1;}sum
}
fn immutable(n:i64,rounds:i64,seed:i64)->i64 {
 let mut sum=0;let mut r=0;
 while r<rounds {let mut text=String::new();let mut i=0;
  while i<n {let mut next=String::with_capacity(text.len()+1);next.push_str(&text);next.push((65+(i+seed+r)%26) as u8 as char);text=next;i+=1;}
  assert_eq!(text.len(),n as usize);sum+=weighted(text.as_bytes(),r%13);r+=1;}sum
}
fn immutable_view(n:i64,rounds:i64,seed:i64)->i64 {
 let mut sum=0;let mut r=0;
 while r<rounds {let mut text=String::new();let mut i=0;
  while i<n {let mut next=String::with_capacity(text.len()+1);next.push_str(&text);next.push((65+(i+seed+r)%26) as u8 as char);text=next;i+=1;}
  assert_eq!(text.len(),n as usize);sum+=weighted(text.as_bytes(),r%13);r+=1;
 }sum
}
fn main() {
 let args:Vec<String>=env::args().collect();let mode=&args[1];let n=args[2].parse().unwrap();let rounds=args[3].parse().unwrap();let seed=args[4].parse().unwrap();
 let text=if mode=="scan" {pattern(n,seed)} else {String::new()};
 let start=unsafe{bench_clock_ns()};let n=unsafe{bench_observe_i64(n)};let rounds=unsafe{bench_observe_i64(rounds)};let seed=unsafe{bench_observe_i64(seed)};let checksum=match mode.as_str(){"lcg"=>lcg(n,rounds,seed),"primes"=>primes(n,rounds,seed),"scan"=>scan(text.as_bytes(),rounds,seed),"builder"=>builder(n,rounds,seed),"immutable"=>immutable(n,rounds,seed),"immutable_view"=>immutable_view(n,rounds,seed),_=>panic!("unknown workload")};
 let checksum=unsafe{bench_observe_i64(checksum)};let elapsed=unsafe{bench_clock_ns()}-start;println!("{}\n{}",checksum,elapsed);
}
