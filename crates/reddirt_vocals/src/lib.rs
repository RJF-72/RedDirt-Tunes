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

    /// Parse a note string like "A4", "C#3", "Bb5" into a MIDI note number.
    fn note_to_midi(note: &str) -> Option<u8> {
        let mut chars = note.chars();
        let letter = chars.next()?;
        let mut alter = 0i8;
        let mut octave_str = String::new();
        for ch in chars {
            match ch {
                '#' => alter += 1,
                'b' | '♭' => alter -= 1,
                d if d.is_ascii_digit() || d == '-' => octave_str.push(d),
                _ => {}
            }
        }
        let octave: i8 = octave_str.parse().ok()?;
        let base = match letter.to_ascii_uppercase() {
            'C' => 0,
            'D' => 2,
            'E' => 4,
            'F' => 5,
            'G' => 7,
            'A' => 9,
            'B' => 11,
            _ => return None,
        };
        let midi = (octave + 1) * 12 + base + alter;
        if midi < 0 || midi > 127 {
            return None;
        }
        Some(midi as u8)
    }

    /// Render a vocal track.
    /// If a neural vocoder backend is available, delegates to it;
    /// otherwise returns silence.
    pub fn render(&self, track: &VocalTrack) -> Result<RenderedVocal, VocalError> {
        let total_ms: u32 = track.phonemes.iter().map(|p| p.params.duration_ms).sum();
        let sample_rate = 48000u32;
        let total_samples = ((total_ms as f32 / 1000.0) * sample_rate as f32) as usize;

        // Try to use real backend
        if let Some(backend) = crate::backend::VocoderBackend::discover() {
            let notes: Vec<(u8, f32)> = track
                .phonemes
                .iter()
                .map(|p| {
                    let midi = Self::note_to_midi(&p.note).unwrap_or(69);
                    // Convert ms to beats at 65 BPM (beat_duration = 60/65 ≈ 0.923s)
                    let beat = (p.params.duration_ms as f32 / 1000.0) / (60.0 / 65.0);
                    (midi, beat)
                })
                .collect();
            let lyrics = track.phonemes.iter().map(|p| p.text.clone()).collect::<Vec<_>>().join(" ");
            match backend.sing(&lyrics, &notes, &track.singer_id, &track.emotion) {
                Ok(path) => {
                    // Read the WAV returned by the server
                    return Self::read_wav(&path, sample_rate);
                }
                Err(e) => {
                    eprintln!("[VOCAL] Backend sing failed: {}. Falling back to silence.", e);
                }
            }
        }

        // Silence fallback
        let buf = vec![0.0f32; total_samples];
        Ok(RenderedVocal {
            samples_l: buf.clone(),
            samples_r: buf,
            sample_rate,
            duration_ms: total_ms,
        })
    }

    /// Read a WAV file and return a RenderedVocal.
    /// Public for use by the mastering pipeline.
    pub fn load_wav(path: &str, expected_sr: u32) -> Result<RenderedVocal, VocalError> {
        Self::read_wav(path, expected_sr)
    }

    fn read_wav(path: &str, expected_sr: u32) -> Result<RenderedVocal, VocalError> {
        use hound::WavReader;
        let reader = WavReader::open(path).map_err(|e| VocalError::RenderFailed(format!("WAV open: {}", e)))?;
        let spec = reader.spec();
        if spec.sample_rate != expected_sr {
            return Err(VocalError::RenderFailed(format!("Sample rate mismatch: got {}, expected {}", spec.sample_rate, expected_sr)));
        }
        let samples: Vec<f32> = match spec.sample_format {
            hound::SampleFormat::Float => reader.into_samples::<f32>().filter_map(|s| s.ok()).collect(),
            hound::SampleFormat::Int => {
                let max_val = (1i32 << (spec.bits_per_sample - 1)) as f32;
                reader.into_samples::<i32>().filter_map(|s| s.ok()).map(|s| s as f32 / max_val).collect()
            }
        };
        let total_samples = samples.len();
        let duration_ms = ((total_samples / spec.channels as usize) as f32 / expected_sr as f32 * 1000.0) as u32;
        if spec.channels == 1 {
            Ok(RenderedVocal {
                samples_l: samples.clone(),
                samples_r: samples,
                sample_rate: expected_sr,
                duration_ms,
            })
        } else if spec.channels == 2 {
            let (l, r): (Vec<f32>, Vec<f32>) = samples.chunks_exact(2).map(|c| (c[0], c[1])).unzip();
            Ok(RenderedVocal {
                samples_l: l,
                samples_r: r,
                sample_rate: expected_sr,
                duration_ms,
            })
        } else {
            Err(VocalError::RenderFailed(format!("Unsupported channel count: {}", spec.channels)))
        }
    }

    /// Return a silent buffer of a given duration in ms.
    pub fn render_silence(&self, duration_ms: u32) -> Vec<f32> {
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
