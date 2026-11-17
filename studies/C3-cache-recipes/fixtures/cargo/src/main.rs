use clap::Parser;
use serde::Serialize;

#[derive(Parser)]
struct Args {}

#[derive(Serialize)]
struct Out { ok: bool, n: u32 }

#[tokio::main]
async fn main() {
    let _ = Args::parse();
    let re = regex::Regex::new(r"c\d").unwrap();
    let n: u32 = rand::random::<u32>() % 10;
    println!("{} {}", re.is_match("c3"), serde_json::to_string(&Out { ok: true, n }).unwrap());
}
