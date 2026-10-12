use std::collections::VecDeque;
use std::env;
use std::sync::{Arc, Condvar, Mutex, atomic::{AtomicU64, Ordering}};
use std::thread;
use std::hint::spin_loop;
use std::time::Instant;
const CAPACITY: usize = 256;
struct Mailbox { queue: Mutex<VecDeque<(i32,u64)>>, changed: Condvar }
impl Mailbox {
    fn send(&self, msg:(i32,u64)) {
        loop { let mut q=self.queue.lock().unwrap(); if q.len()<CAPACITY { q.push_back(msg); self.changed.notify_all(); return; } drop(q); thread::yield_now(); spin_loop(); }
    }
    fn recv(&self)->(i32,u64) { let mut q=self.queue.lock().unwrap(); while q.is_empty() { q=self.changed.wait(q).unwrap(); } q.pop_front().unwrap() }
}
fn main() {
    let a:Vec<String>=env::args().collect(); assert_eq!(a.len(),3);
    let count:u64=a[1].parse().unwrap(); let receivers:usize=a[2].parse().unwrap(); assert!(count>0&&count<=10_000_000&&receivers>0&&receivers<=64);
    let mb=Arc::new(Mailbox{queue:Mutex::new(VecDeque::with_capacity(CAPACITY)),changed:Condvar::new()});
    let seen:Vec<AtomicU64>=(0..count).map(|_|AtomicU64::new(0)).collect(); let seen=Arc::new(seen); let sum=Arc::new(AtomicU64::new(0)); let consumed=Arc::new(AtomicU64::new(0));
    let mut joins=Vec::new();
    for _ in 0..receivers { let m=mb.clone();let s=seen.clone();let sm=sum.clone();let c=consumed.clone();joins.push(thread::spawn(move|| loop { let (tag,id)=m.recv(); if tag==0 {break;} if tag!=1||id>=s.len() as u64 { panic!("invalid message"); } s[id as usize].fetch_add(1,Ordering::Relaxed);sm.fetch_add(id,Ordering::Relaxed);c.fetch_add(1,Ordering::Relaxed); })); }
    let start=Instant::now(); for id in 0..count {mb.send((1,id));} for _ in 0..receivers {mb.send((0,0));} for j in joins {j.join().unwrap();} let elapsed=start.elapsed().as_secs_f64();
    let bad=seen.iter().filter(|x|x.load(Ordering::Relaxed)!=1).count();let got=consumed.load(Ordering::Relaxed);let actual=sum.load(Ordering::Relaxed);let expected=count*(count-1)/2;
    println!("runtime,receivers,messages,wall_s,msg_per_s,consumed,checksum,missing_or_duplicate");println!("Rust,{receivers},{count},{elapsed:.6},{:.0},{got},{actual},{bad}",count as f64/elapsed);
    assert!(got==count&&actual==expected&&bad==0,"mailbox integrity check failed");
}
