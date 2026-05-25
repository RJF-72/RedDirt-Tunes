use std::path::Path;

/// Singing Vocal Synthesis Engine
/// Takes lyrics, melody, and emotion parameters and produces a sung audio buffer.
/// NOTE: This is an API facade only. Real vocal rendering is delegated to an external
/// neural vocoder backend (DiffSinger, N-Singer, etc.). The render function returns silence
/// until a real backend is plugged in.
pub struct VocalSynthesizer;

#[derive(Debug, Clone)]
pub struct VocalParams {
    pub pitch_hz: f32,
    pub duration_ms: u32,
    pub velocity: f32,
    pub vibrato_rate: f32,
    pub vibrato_depth: f32,
    pub breathiness: f32,
    pub formant_shift: f32,
}

#[derive(Debug, Clone)]
pub struct SungPhoneme {
    pub text: String,
    pub note: String,
    pub params: VocalParams,
}

#[derive(Debug, Clone)]
pub struct VocalTrack {
    pub phonemes: Vec<SungPhoneme>,
    pub singer_id: String,
    pub emotion: String,
}

#[derive(Debug, Clone)]
pub struct RenderedVocal {
    pub samples_l: Vec<f32>,
    pub samples_r: Vec<f32>,
    pub sample_rate: u32,
    pub duration_ms: u32,
}

impl VocalSynthesizer {
    pub fn new() -> Self {
        Self
    }

    /// Render a vocal track.
    /// Currently returns silence — a neural vocoder backend must be plugged in for actual sound.
    pub fn render(&self,
        track: &VocalTrack,
    ) -> Result<RenderedVocal, VocalError> {
        let total_ms: u32 = track.phonemes.iter().map(|p| p.params.duration_ms).sum();
        let sample_rate = 48000u32;
        let total_samples = ((total_ms as f32 / 1000.0) * sample_rate as f32) as usize;

        // Silence buffer. Real audio comes from an external vocoder (DiffSinger, N-Singer, etc.).
        let buf = vec![0.0f32; total_samples];

        Ok(RenderedVocal {
            samples_l: buf.clone(),
            samples_r: buf,
            sample_rate,
            duration_ms: total_ms,
        })
    }

    /// Return a silent buffer of a given duration in ms.
    pub fn render_silence(&self, duration_ms: u32
    ) -> Vec<f32> {
        let sample_rate = 48000u32;
        let total_samples = ((duration_ms as f32 / 1000.0) * sample_rate as f32) as usize;
        vec![0.0f32; total_samples]
    }

    /// Check if a real vocoder backend (not local silence) is available.
    pub fn is_real() -> bool {
        crate::backend::VocoderBackend::is_available()
    }
}

pub mod backend;

#[derive(Debug, thiserror::Error)]
pub enum VocalError {
    #[error("Failed to render vocal: {0}")]
    RenderFailed(String),
    #[error("Singer not found: {0}")]
    SingerNotFound(String),
}

#[test]
fn test_vocal_synth() {
    let synth = VocalSynthesizer::new();
    let track = VocalTrack {
        phonemes: vec![
            SungPhoneme {
                text: "La".into(),
                note: "A3".into(),
                params: VocalParams {
                    pitch_hz: 220.0,
                    duration_ms: 500,
                    velocity: 0.8,
                    vibrato_rate: 5.5,
                    vibrato_depth: 0.3,
                    breathiness: 0.2,
                    formant_shift: 0.0,
                },
            },
        ],
        singer_id: "default".into(),
        emotion: "sad".into(),
    };
    let result = synth.render(&track).unwrap();
    // Buffer is silence until real vocoder is plugged in
    assert_eq!(result.samples_l.len(), 24_000); // 500ms at 48kHz
    assert_eq!(result.sample_rate, 48000);
    assert!(result.samples_l.iter().all(|s| *s == 0.0));
}
