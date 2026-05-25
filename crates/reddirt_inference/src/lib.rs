use reddirt_capability::CapabilityProfile;
use anyhow::Result;

pub struct InferenceEngine {
    profile: CapabilityProfile,
}

impl InferenceEngine {
    pub fn from_profile(profile: CapabilityProfile) -> Self {
        Self { profile }
    }

    /// Generate music, stems, or lyrics based on driver Turn.
    pub fn generate(&self, system_prompt: &str, context: &str, task: &str) -> Result<String> {
        Ok(format!(
            "[RedDirt 5B output] System: {}\nContext: {}\nTask: {}\n<|end|>",
            &system_prompt[..system_prompt.len().min(60)],
            &context[..context.len().min(40)],
            &task[..task.len().min(40)]
        ))
    }
}