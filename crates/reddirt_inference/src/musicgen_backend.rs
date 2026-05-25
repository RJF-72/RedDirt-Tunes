use anyhow::Result;
use lariat_capability::CapabilityProfile;
use crate::backend::{Backend, GenerationParams};
use serde::{Deserialize, Serialize};
use std::process::Command;

/// MusicGen backend: calls a Python server with MusicGen loaded.
/// The server is a separate Python process that holds the model in VRAM.
/// Rust only sends text prompts and receives audio file paths.
pub struct MusicGenBackend {
    server_url: String,
    model_name: String,
}

impl MusicGenBackend {
    pub fn discover() -> Option<Self> {
        // Check if the Python server is running
        if Self::server_is_alive("127.0.0.1", 8765) {
            Some(Self {
                server_url: "http://127.0.0.1:8765".into(),
                model_name: "facebook/musicgen-small".into(),
            })
        } else {
            None
        }
    }

    fn server_is_alive(host: &str, port: u16) -> bool {
        // Lightweight check: try to connect to the health endpoint
        match ureq::get(&format!("http://{}:{}/health", host, port)).call() {
            Ok(resp) => resp.status() == 200,
            Err(_) => false,
        }
    }

    pub fn launch_server(&self,
        python_env: Option<&str>,
    ) -> Result<std::process::Child> {
        let mut cmd = Command::new(python_env.unwrap_or("python"));
        cmd.arg("training/musicgen_server.py")
            .arg("--model")
            .arg(&self.model_name)
            .arg("--port")
            .arg("8765")
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped());
        
        let child = cmd.spawn()
            .map_err(|e| anyhow::anyhow!("Failed to start MusicGen server: {}", e))?;
        
        // Wait a few seconds for server to start
        std::thread::sleep(std::time::Duration::from_secs(10));
        
        Ok(child)
    }
}

#[derive(Debug, Serialize)]
struct GenRequest {
    prompt: String,
    duration: u32,
    key: String,
    tempo: u32,
    mode: String,
}

#[derive(Debug, Deserialize)]
struct GenResponse {
    status: String,
    audio_path: String,
    metadata: serde_json::Value,
}

impl Backend for MusicGenBackend {
    fn generate(
        &self,
        prompt: &str,
        params: &GenerationParams,
    ) -> Result<String> {
        let req = GenRequest {
            prompt: prompt.into(),
            duration: (params.max_tokens / 50).clamp(5, 60) as u32,
            key: "Am".into(),
            tempo: 65,
            mode: "GENERATION".into(),
        };
        
        let resp = ureq::post(&format!("{}/generate", self.server_url))
            .send_json(serde_json::to_value(req)?)
            .map_err(|e| anyhow::anyhow!("MusicGen request failed: {}", e))?;
        
        let body: GenResponse = resp
            .into_json()
            .map_err(|e| anyhow::anyhow!("MusicGen response parse failed: {}", e))?;
        
        if body.status != "ok" {
            anyhow::bail!("MusicGen generation failed: {}", body.status);
        }
        
        Ok(format!(
            "GENERATED: {} | MODEL: {} | META: {}",
            body.audio_path, self.model_name, body.metadata
        ))
    }
}
