use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub const TRAJECTORIES_DIR: &str = ".reddirt/training/trajectories";

pub mod song_state;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Step {
    pub mode: String,
    pub observation_refs: Vec<String>,
    pub output: String,
    pub tools_used: Vec<ToolCall>,
    pub env_feedback: EnvFeedback,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rewards: Option<Rewards>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCall {
    pub tool: String,
    pub args: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnvFeedback {
    pub audio_outcome: AudioOutcome,
    pub latency_ms: u32,
    pub memory_used_mb: u32,
    pub stem_count: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum AudioOutcome {
    Rendered(Vec<String>),
    Failed(Vec<String>),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Rewards {
    pub render: f64,
    pub latency_penalty: f64,
    pub memory_penalty: f64,
    pub stem_clarity: f64,
    pub nlp_quality: f64,
    pub total: f64,
}

pub mod io;
// io.rs content omitted for brevity, using same pattern as TITAN