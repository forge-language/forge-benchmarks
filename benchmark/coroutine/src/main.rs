use std::{env, ffi::CString};
unsafe extern "C" {
    fn bench_config(argc: i32, argv: *const *const std::ffi::c_char);
    fn bench_arg(index: i64) -> i64;
    fn bench_clock_ns() -> i64;
    fn bench_observe_i64(value: i64) -> i64;
    fn bench_prepare();
    fn bench_result(id: i64, value: i64);
    fn bench_finish(start: i64) -> i32;
}
async fn worker(id: i64, rounds: i64, chunk: i64, seed: i64) {
    let mut value = seed + id;
    for _ in 0..rounds {
        for _ in 0..chunk { value = (value * 48271) % 2147483647; }
        tokio::task::yield_now().await;
    }
    unsafe { bench_result(id, value) };
}
fn main() {
    let args: Vec<_> = env::args().map(|arg| CString::new(arg).unwrap()).collect();
    let pointers: Vec<_> = args.iter().map(|arg| arg.as_ptr()).collect();
    unsafe { bench_config(pointers.len() as i32, pointers.as_ptr()) };
    let workers = unsafe { bench_arg(0) };
    let start = unsafe { bench_clock_ns() };
    unsafe { bench_prepare() };
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(workers as usize).build().unwrap();
    assert_eq!(runtime.metrics().num_workers(), workers as usize);
    runtime.block_on(async {
        let tasks = unsafe { bench_observe_i64(bench_arg(1)) };
        let rounds = unsafe { bench_observe_i64(bench_arg(2)) };
        let chunk = unsafe { bench_observe_i64(bench_arg(3)) };
        let seed = unsafe { bench_observe_i64(bench_arg(4)) };
        // A JoinHandle per task makes completion explicit; all handles are
        // awaited, and every task-id/result is independently checked later.
        let mut handles = Vec::with_capacity(tasks as usize);
        for id in 0..tasks { handles.push(tokio::spawn(worker(id, rounds, chunk, seed))); }
        for handle in handles { handle.await.unwrap(); }
    });
    drop(runtime);
    let status = unsafe { bench_finish(start) };
    if status != 0 { std::process::exit(status); }
}
