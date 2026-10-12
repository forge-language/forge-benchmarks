//! Shared, fixed-count closed-loop load observer. Never linked into a server.
use std::io::{Read, Write};
use std::net::TcpStream;
use std::sync::{Arc, Barrier};
use std::time::{Duration, Instant};

fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(args.len(), 7);
    let port: u16 = args[1].parse().unwrap();
    let concurrency: usize = args[2].parse().unwrap();
    let requests: usize = args[3].parse().unwrap();
    let seed: usize = args[4].parse().unwrap();
    let response = Arc::new(std::fs::read(&args[5]).unwrap());
    let output = args[6].clone();
    assert!(requests >= concurrency && concurrency > 0);
    let barrier = Arc::new(Barrier::new(concurrency + 1));
    let mut handles = Vec::new();
    for lane in 0..concurrency {
        let response = Arc::clone(&response);
        let barrier = Arc::clone(&barrier);
        handles.push(std::thread::spawn(move || {
            let mut records = Vec::with_capacity(requests / concurrency + 1);
            let mut buffer = Vec::with_capacity(response.len() + 1);
            barrier.wait();
            for id in (lane..requests).step_by(concurrency) {
                let padding = "x".repeat(32 + (seed + id) % 512);
                let request = format!("GET /bench/{seed}/{id} HTTP/1.1\r\nHost: localhost\r\nX-Input: {padding}\r\nConnection: close\r\n\r\n");
                let start = Instant::now();
                buffer.clear();
                let result = (|| -> std::io::Result<()> {
                    let mut stream = TcpStream::connect(("127.0.0.1", port))?;
                    stream.set_nodelay(true)?;
                    stream.set_read_timeout(Some(Duration::from_secs(10)))?;
                    stream.set_write_timeout(Some(Duration::from_secs(10)))?;
                    stream.write_all(request.as_bytes())?;
                    stream.take(response.len() as u64 + 1).read_to_end(&mut buffer)?;
                    if buffer != *response { return Err(std::io::ErrorKind::InvalidData.into()); }
                    Ok(())
                })();
                let elapsed = start.elapsed().as_nanos();
                let error = result.err().map(|value| format!("{value:?}")).unwrap_or_default();
                records.push((id, elapsed, buffer.len(), error));
            }
            records
        }));
    }
    println!("ready");
    std::io::stdout().flush().unwrap();
    let mut signal = String::new();
    std::io::stdin().read_line(&mut signal).unwrap();
    assert_eq!(signal.trim(), "go");
    let started = Instant::now();
    barrier.wait();
    let mut records = Vec::with_capacity(requests);
    for handle in handles {
        records.extend(handle.join().unwrap());
    }
    let elapsed = started.elapsed().as_nanos();
    records.sort_unstable_by_key(|record| record.0);
    let mut file = std::io::BufWriter::new(std::fs::File::create_new(output).unwrap());
    writeln!(file, "id\tlatency_ns\tresponse_bytes\terror").unwrap();
    let errors = records.iter().filter(|record| !record.3.is_empty()).count();
    for (id, latency, bytes, error) in records {
        writeln!(file, "{id}\t{latency}\t{bytes}\t{error}").unwrap();
    }
    file.flush().unwrap();
    println!("{elapsed}\t{requests}\t{errors}");
}
