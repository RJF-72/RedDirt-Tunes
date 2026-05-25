use serde::{Deserialize, Serialize};
use anyhow::Result;
use std::time::Duration;

/// Remote HTTP vocoder backend (DiffSinger / So-VITS-SVC / Fish Speech)
pub struct VocoderBackend {
    url: String,
}

#[derive(Debug, Clone, Serialize)]
struct SingRequest {
    lyrics: String,
    notes: Vec<Note>,
    singer_id: String,
    emotion: String,
    output_dir: String,
}

#[derive(Debug, Clone, Deserialize)]
struct SingResponse {
    status: String,
    audio_path: String,
    backend: String,
    metadata: SingMetadata,
}

#[derive(Debug, Clone, Deserialize)]
struct SingMetadata {
    lyrics: String,
    singer: String,
    emotion: String,
    num_notes: usize,
}

#[derive(Debug, Clone, Serialize)]
struct Note {
    pitch: u8,
    duration_beat: f32,
}

impl VocoderBackend {
    pub fn discover() -> Option<Self> {
        let url = "http://127.0.0.1:8766".to_string();
        match Self::health_check(&url) {
            Ok(status) => {
                if status.status == "ok" {
                    println!("[vocoder] Backend discovered: {}", status.backend);
                    Some(Self { url })
                } else {
                    None
                }
            }
            Err(_) => {
                println!("[vocoder] No vocoder server on port 8766. Singing will return silence.");
                None
            }
        }
    }

    fn health_check(url: &str) -> Result<HealthStatus> {
        let resp = ureq::get(&format!("{}/health", url))
            .timeout(Duration::from_secs(5))
            .call()
            .map_err(|e| anyhow::anyhow!("Health check failed: {}", e))?;
        let status: HealthStatus = resp
            .into_json()
            .map_err(|e| anyhow::anyhow!("Parse failed: {}", e))?;
        Ok(status)
    }

    pub fn sing(
        &self,
        lyrics: &str,
        notes: &[(u8, f32)], // (pitch, duration_beat)
        singer_id: &str,
        emotion: &str,
    ) -> Result<String> {
        let notes_vec: Vec<Note> = notes
            .iter()
            .map(|(pitch, dur)| Note {
                pitch: *pitch,
                duration_beat: *dur,
            })
            .collect();

        let req = SingRequest {
            lyrics: lyrics.into(),
            notes: notes_vec,
            singer_id: singer_id.into(),
            emotion: emotion.into(),
            output_dir: ".reddirt/output".into(),
        };

        let resp = ureq::post(&format!("{}/sing", self.url))
            .timeout(Duration::from_secs(120))
            .send_json(serde_json::to_value(req)?)
            .map_err(|e| anyhow::anyhow!("Sing request failed: {}", e))?;

        let body: SingResponse = resp
            .into_json()
            .map_err(|e| anyhow::anyhow!("Failed to parse sing response: {}", e))?;

        if body.status != "ok" {
            anyhow::bail!("Singing failed: {}", body.status);
        }

        Ok(body.audio_path)
    }

    pub fn is_available() -> bool {
        Self::discover().is_some()
    }
}

#[derive(Debug, Clone, Deserialize)]
struct HealthStatus {
    status: String,
    backend: String,
}
