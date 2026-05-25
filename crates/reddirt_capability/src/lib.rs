use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Tier {
    Studio,
    Live,
    Mobile,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioLimits {
    pub max_stems: u32,
    pub max_model_mem_mb: u32,
    pub max_context_tokens: u32,
    pub max_kv_cache_mb: u32,
    pub max_buffer_ms: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeatureFlags {
    pub stem_separation_enabled: bool,
    pub real_time_processing: bool,
    pub nlp_enhanced: bool,
    pub nlu_enhanced: bool,
    pub lyric_generation: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapabilityProfile {
    pub ram_total_mb: u32,
    pub ram_free_mb: u32,
    pub audio_interface: AudioInterface,
    pub sample_rate_hz: u32,
    pub max_channels: u8,
    pub tier: Tier,
    pub limits: AudioLimits,
    pub features: FeatureFlags,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AudioInterface {
    Asio,
    Wasapi,
    CoreAudio,
    Alsa,
    Jack,
    None,
}

impl CapabilityProfile {
    pub fn probe() -> Self {
        Self {
            ram_total_mb: 32768,
            ram_free_mb: 16384,
            audio_interface: AudioInterface::Wasapi,
            sample_rate_hz: 48000,
            max_channels: 2,
            tier: Tier::Studio,
            limits: AudioLimits {
                max_stems: 64,
                max_model_mem_mb: 5000,
                max_context_tokens: 8192,
                max_kv_cache_mb: 2048,
                max_buffer_ms: 256,
            },
            features: FeatureFlags {
                stem_separation_enabled: true,
                real_time_processing: true,
                nlp_enhanced: true,
                nlu_enhanced: true,
                lyric_generation: true,
            },
        }
    }
}