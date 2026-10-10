use std::{env, thread};
unsafe extern "C" {
    fn bench_clock_ns() -> i64;
    fn bench_observe_i64(value: i64) -> i64;
    fn bench_reset();
    fn bench_result(value: i64);
    fn bench_total() -> i64;
    fn bench_count() -> i64;
}
fn worker(id: i64, total: i64) {
    // Match Forge's public callback contract: parameters are read by each
    // worker after it starts; parsing and observer costs are in both timings.
    let args: Vec<String> = env::args().collect();
    let n = unsafe { bench_observe_i64(args[2].parse().unwrap()) };
    let rounds = unsafe { bench_observe_i64(args[3].parse().unwrap()) };
    let seed = unsafe { bench_observe_i64(args[4].parse().unwrap()) };
    let work = n / total + i64::from(id < n % total);
    let mut value = seed + id;
    for _ in 0..rounds {
        for _ in 0..work { value = (value * 48271) % 2147483647; }
    }
    unsafe { bench_result(value) };
}
fn main() {
    let args: Vec<String> = env::args().collect();
    let threads: i64 = args[1].parse().unwrap();
    assert!((1..=4).contains(&threads));
    unsafe { bench_reset() };
    let start = unsafe { bench_clock_ns() };
    let handles: Vec<_> = (0..threads).map(|id| thread::spawn(move || worker(id, threads))).collect();
    for handle in handles { handle.join().unwrap(); }
    let result = unsafe { bench_observe_i64(bench_total()) };
    let elapsed = unsafe { bench_clock_ns() } - start;
    assert_eq!(unsafe { bench_count() }, threads);
    println!("{result}\n{elapsed}");
}
