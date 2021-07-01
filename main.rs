use std::process::Command;
fn main() {
  println!("test");
  Command::new("neofetch")
        .spawn()
}
