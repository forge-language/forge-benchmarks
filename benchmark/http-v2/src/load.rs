//! V2 observer: bounded connects, stage durations, immediately retained rows.
//! This separately versioned protocol is not comparable silently with V1.
use std::io::{self, Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::sync::{Arc, Barrier, Mutex};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(args.len(), 8);
    let port: u16 = args[1].parse().unwrap();
    let concurrency: usize = args[2].parse().unwrap();
    let requests: usize = args[3].parse().unwrap();
    let seed: usize = args[4].parse().unwrap();
    let response = Arc::new(std::fs::read(&args[5]).unwrap());
    let connect_timeout = Duration::from_millis(args[7].parse().unwrap());
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    assert!(requests >= concurrency && concurrency > 0 && !connect_timeout.is_zero());
    let mut file = std::fs::File::create_new(&args[6]).unwrap();
    writeln!(file, "id\tlatency_ns\tconnect_ns\tsetup_ns\twrite_ns\tread_ns\teof_ns\tresponse_bytes\tfailed_stage\terror").unwrap();
    // Unbuffered writes retain every completed observation if the parent later
    // kills the process. File::write_all persists into the kernel page cache,
    // without promising power-loss durability; no fsync in the measured loop.
    let file = Arc::new(Mutex::new(file));
    let stop = Arc::new(AtomicBool::new(false));
    let barrier = Arc::new(Barrier::new(concurrency + 1));
    let mut handles = Vec::new();
    for lane in 0..concurrency {
        let response = Arc::clone(&response);
        let barrier = Arc::clone(&barrier);
        let file = Arc::clone(&file);
        let stop = Arc::clone(&stop);
        handles.push(std::thread::spawn(move || {
            let mut attempts = 0usize;
            let mut errors = 0usize;
            let mut buffer = Vec::with_capacity(response.len() + 1);
            let mut scratch = [0u8; 8192];
            barrier.wait();
            for id in (lane..requests).step_by(concurrency) {
                // A failed request stops later, unattempted requests. All
                // in-flight requests still finish or time out and are recorded.
                if stop.load(Ordering::Relaxed) { break; }
                let padding = "x".repeat(32 + (seed + id) % 512);
                let request = format!("GET /bench/{seed}/{id} HTTP/1.1\r\nHost: localhost\r\nX-Input: {padding}\r\nConnection: close\r\n\r\n");
                let start = Instant::now();
                let mut connect_ns = 0;
                let mut setup_ns = 0;
                let mut write_ns = 0;
                let mut read_ns = 0;
                let mut eof_ns = 0;
                let mut stage = "connect";
                buffer.clear();
                let result = (|| -> io::Result<()> {
                    let tick = Instant::now();
                    let connected = TcpStream::connect_timeout(&address, connect_timeout);
                    connect_ns = tick.elapsed().as_nanos();
                    let mut stream = connected?;
                    stage = "setup";
                    let tick = Instant::now();
                    let configured = (|| -> io::Result<()> {
                        stream.set_nodelay(true)?;
                        stream.set_read_timeout(Some(Duration::from_secs(10)))?;
                        stream.set_write_timeout(Some(Duration::from_secs(10)))?;
                        Ok(())
                    })();
                    setup_ns = tick.elapsed().as_nanos();
                    configured?;
                    stage = "write";
                    let tick = Instant::now();
                    let sent = stream.write_all(request.as_bytes());
                    write_ns = tick.elapsed().as_nanos();
                    sent?;
                    stage = "read";
                    let tick = Instant::now();
                    let read = (|| -> io::Result<()> {
                        while buffer.len() < response.len() {
                            let wanted = (response.len() - buffer.len()).min(scratch.len());
                            let count = match stream.read(&mut scratch[..wanted]) {
                                Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
                                value => value?,
                            };
                            if count == 0 { return Err(io::ErrorKind::UnexpectedEof.into()); }
                            buffer.extend_from_slice(&scratch[..count]);
                        }
                        Ok(())
                    })();
                    read_ns = tick.elapsed().as_nanos();
                    read?;
                    stage = "eof";
                    let tick = Instant::now();
                    let closed = (|| -> io::Result<()> {
                        loop {
                            match stream.read(&mut scratch[..1]) {
                                Ok(0) => return Ok(()),
                                Ok(_) => {
                                    buffer.push(scratch[0]);
                                    return Err(io::ErrorKind::InvalidData.into());
                                }
                                Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
                                Err(error) => return Err(error),
                            }
                        }
                    })();
                    eof_ns = tick.elapsed().as_nanos();
                    closed?;
                    stage = "response";
                    if buffer != *response { return Err(io::ErrorKind::InvalidData.into()); }
                    Ok(())
                })();
                let elapsed = start.elapsed().as_nanos();
                let (failed_stage, error) = match result {
                    Ok(()) => ("", String::new()),
                    Err(error) => {
                        errors += 1;
                        stop.store(true, Ordering::Relaxed);
                        (stage, format!("{error:?}"))
                    }
                };
                attempts += 1;
                let record = format!("{id}\t{elapsed}\t{connect_ns}\t{setup_ns}\t{write_ns}\t{read_ns}\t{eof_ns}\t{}\t{failed_stage}\t{error}\n", buffer.len());
                file.lock().unwrap().write_all(record.as_bytes()).unwrap();
            }
            (attempts, errors)
        }));
    }
    println!("ready");
    io::stdout().flush().unwrap();
    let mut signal = String::new();
    io::stdin().read_line(&mut signal).unwrap();
    assert_eq!(signal.trim(), "go");
    let started = Instant::now();
    barrier.wait();
    let mut attempts = 0;
    let mut errors = 0;
    for handle in handles {
        let (completed, failed) = handle.join().unwrap();
        attempts += completed;
        errors += failed;
    }
    let elapsed = started.elapsed().as_nanos();
    println!("{elapsed}\t{attempts}\t{errors}");
}
