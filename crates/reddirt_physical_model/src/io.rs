use std::fs;
use std::path::{Path, PathBuf};
use crate::{Step, Rewards};

pub fn ensure_dir(p: &Path) -> std::io::Result<()> {
    if !p.exists() {
        fs::create_dir_all(p)?;
    }
    Ok(())
}

pub fn write_step(dir: &Path, name: &str, step: &Step) -> std::io::Result<()> {
    let path = dir.join(name);
    let json = serde_json::to_string_pretty(step)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    fs::write(path, json)
}
