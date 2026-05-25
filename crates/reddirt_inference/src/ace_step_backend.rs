use anyhow::Result;
use std::time::Duration;
use serde::{Deserialize, Serialize};

/// Client for the ACE-Step Python model server.
pub struct AceStepBackend {
    url: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct HealthStatus {
    pub status: String,
    pub backend: String,
    pub model: String,
    pub device: String,
}

#[derive(Debug, Clone, Serialize)]
struct GenerateRequest {
    prompt: String,
    duration: u16,
    key: String,
    tempo: u16,
    mode: String,
}

#[derive(Debug, Clone, Deserialize)]
struct GenerateResponse {
    status: String,
    audio_path: String,
    backend: String,
    metadata: GenerateMetadata,
}

#[derive(Debug, Clone, Deserialize)]
struct GenerateMetadata {
    prompt: String,
    duration: u16,
    key: String,
    tempo: u16,
    mode: String,
}

impl AceStepBackend {
    pub fn discover() -> Result<Self> {
        let url = "http://127.0.0.1:8765".to_string();
        match Self::health_check(&url) {
            Ok(status) => {
                if status.status == "ok" {
                    println!(
                        "[ace-step] Server healthy: {} | model: {} | device: {}",
                        status.backend, status.model, status.device
                    );
                    Ok(Self { url })
                } else {
                    Err(anyhow::anyhow!("Server unhealthy: {:?}", status))
                }
            }
            Err(e) => Err(anyhow::anyhow!("Cannot reach ACE-Step server: {}", e)),
        }
    }

    pub fn url(&self) -> &str {
        &self.url
    }

    fn health_check(url: &str) -> Result<HealthStatus> {
        let resp = ureq::get(&format!("{}/health", url))
            .timeout(Duration::from_secs(5))
            .call()
            .map_err(|e| anyhow::anyhow!("Health check failed: {}", e))?;
        let status: HealthStatus = resp
            .into_json()
            .map_err(|e| anyhow::anyhow!("Failed to parse health: {}", e))?;
        Ok(status)
    }
}

use crate::Backend;
use crate::GenerationResponse;

impl Backend for AceStepBackend {
    fn generate(
        &self,
        prompt: &str,
        key: &str,
        tempo: u16,
        duration_sec: u16,
    ) -> Result<GenerationResponse> {
        let req = GenerateRequest {
            prompt: prompt.into(),
            duration: duration_sec,
            key: key.into(),
            tempo,
            mode: "GENERATION".into(),
        };

        let resp = ureq::post(&format!("{}/generate", self.url))
            .timeout(Duration::from_secs(120))
            .send_json(serde_json::to_value(req)?)
            .map_err(|e| anyhow::anyhow!("Generation request failed: {}", e))?;

        let body: GenerateResponse = resp
            .into_json()
            .map_err(|e| anyhow::anyhow!("Failed to parse generation response: {}", e))?;

        if body.status != "ok" {
            anyhow::bail!("Generation failed: {}", body.status);
        }

        Ok(GenerationResponse {
            audio_path: body.audio_path,
            backend_name: body.backend,
            duration_sec: body.metadata.duration,
            sample_rate: 24000,
        })
    }
}
