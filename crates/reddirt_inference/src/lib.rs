use reddirt_capability::CapabilityProfile;
use anyhow::Result;

pub mod ace_step_backend;
pub use ace_step_backend::{AceStepBackend, HealthStatus};

/// Inference facade for RedDirt-Tunes.
/// The model is external (ACE-Step running in a Python server process).
/// This crate only orchestrates calls and handles responses.
pub struct InferenceEngine {
    profile: CapabilityProfile,
    backend: Option<Box<dyn Backend>>,
}

/// Backend contract for any generation backend (HTTP server, mock, etc.)
pub trait Backend: Send + Sync {
    fn generate(
        &self,
        prompt: &str,
        key: &str,
        tempo: u16,
        duration_sec: u16,
    ) -> Result<GenerationResponse>;
}

/// Response from a generation backend.
#[derive(Debug, Clone)]
pub struct GenerationResponse {
    pub audio_path: String,
    pub backend_name: String,
    pub duration_sec: u16,
    pub sample_rate: u32,
}

impl InferenceEngine {
    pub fn from_profile(profile: CapabilityProfile) -> Self {
        let backend = match AceStepBackend::discover() {
            Ok(b) => {
                println!("[reddirt] ACE-Step backend discovered at {}", b.url());
                Some(Box::new(b) as Box<dyn Backend>)
            }
            Err(e) => {
                println!("[reddirt] ACE-Step not available ({}). Using mock.", e);
                None
            }
        };
        Self { profile, backend }
    }

    /// Generate music from a text description.
    pub fn generate(
        &self,
        system_prompt: &str,
        _context: &str,
        task: &str,
    ) -> Result<GenerationResponse> {
        // Parse musical metadata from the system_prompt
        let (key, tempo) = self.extract_key_tempo(system_prompt);

        match &self.backend {
            Some(backend) => {
                println!("[reddirt] Generating with ACE-Step: {} | {} | {} BPM", task, key, tempo);
                backend.generate(task, &key, tempo, 10)
            }
            None => {
                // Fallback: return a mock path so the UI/framework doesn't crash
                println!("[reddirt] MOCK: Would generate '{}'", task);
                Ok(GenerationResponse {
                    audio_path: ".reddirt/output/mock_generation.wav".into(),
                    backend_name: "mock".into(),
                    duration_sec: 10,
                    sample_rate: 24000,
                })
            }
        }
    }

    fn extract_key_tempo(&self, prompt: &str) -> (String, u16) {
        let mut key = "C".to_string();
        let mut tempo = 120u16;
        if prompt.contains("A minor") || prompt.contains("Am") {
            key = "Am".into();
            tempo = 65;
        } else if prompt.contains("E minor") || prompt.contains("Em") {
            key = "Em".into();
            tempo = 80;
        } else if prompt.contains("major") {
            key = "C".into();
            tempo = 120;
        }
        (key, tempo)
    }
}
