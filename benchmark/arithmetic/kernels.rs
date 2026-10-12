use std::env;
unsafe extern "C" {
    fn bench_clock_ns() -> i64;
    fn bench_observe_i64(value: i64) -> i64;
}
fn probe(n: i64, mut a: i64, mut b: i64, mut sign: i64, alternate: i64) -> i64 {
    if alternate == 2 {
        let mut value = a; let mut i = 0_i64;
        while i < n {
            value = value.wrapping_mul(48271).wrapping_add(1) % 2147483647;
            i += 1;
        }
        return value;
    }
    let mut total = 0_i64; let mut i = 0_i64;
    while i < n {
        let value = a.wrapping_mul(sign);
        total = total.wrapping_add(value / b).wrapping_add(value % b);
        a = a.wrapping_add(17);
        b = b.wrapping_add(11) % 65521 + 1;
        if alternate != 0 { sign = sign.wrapping_neg(); }
        i = i.wrapping_add(1);
    }
    total
}
fn main() {
    let args: Vec<String> = env::args().collect();
    let n = args[1].parse().unwrap(); let a = args[2].parse().unwrap();
    let b = args[3].parse().unwrap(); let sign = args[4].parse().unwrap();
    let alternate = args[5].parse().unwrap();
    let start = unsafe { bench_clock_ns() };
    let n = unsafe { bench_observe_i64(n) }; let a = unsafe { bench_observe_i64(a) };
    let b = unsafe { bench_observe_i64(b) }; let sign = unsafe { bench_observe_i64(sign) };
    let alternate = unsafe { bench_observe_i64(alternate) };
    let result = unsafe { bench_observe_i64(probe(n, a, b, sign, alternate)) };
    let elapsed = unsafe { bench_clock_ns() } - start;
    println!("{}\n{}", result, elapsed);
}
