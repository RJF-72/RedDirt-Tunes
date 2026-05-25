// The living song — the physical model of music.
// Arrangement, section emotions, mix state, stems, lyrics.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A song is a sequence of sections, each with its own emotion, stems, and lyrics.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SongState {
    pub title: String,
    pub description: String,
    pub global_key: String,
    pub global_tempo: u16,
    pub sections: Vec<Section>,
    pub mix: MixState,
    pub emotions: EmotionArc,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Section {
    pub name: String, // "Intro", "Verse 1", "Pre-chorus", "Chorus", "Bridge", "Outro"
    pub kind: SectionKind,
    pub duration_bars: u8,
    pub key: String,
    pub tempo: u16,
    pub emotion: SectionEmotion,
    pub lyrics: String,
    pub stems: HashMap<String, StemState>, // "vocals", "drums", "bass", "guitar", "pads"
    pub melody_notes: Vec<Note>,
    pub chord_progression: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SectionKind {
    Intro,
    Verse,
    PreChorus,
    Chorus,
    Bridge,
    Outro,
    Break,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SectionEmotion {
    pub valence: f32,   // -1.0 (sad) to 1.0 (happy)
    pub arousal: f32,   // 0.0 (calm) to 1.0 (intense)
    pub tension: f32,   // 0.0 (resolved) to 1.0 (suspenseful)
    pub dominance: f32, // 0.0 (submissive/quiet) to 1.0 (dominant/loud)
    pub emotion_tag: String, // "longing", "rage", "bliss", "despair"
}

impl Default for SectionEmotion {
    fn default() -> Self {
        Self {
            valence: 0.0,
            arousal: 0.5,
            tension: 0.5,
            dominance: 0.5,
            emotion_tag: "neutral".into(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Note {
    pub pitch: u8,     // MIDI note number
    pub velocity: u8,  // 0-127
    pub start_beat: f32,
    pub duration_beat: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StemState {
    pub present: bool,
    pub volume_db: f32,
    pub pan: f32,      // -1.0 left to 1.0 right
    pub muted: bool,
    pub effects: Vec<Effect>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Effect {
    pub kind: EffectKind,
    pub params: HashMap<String, f32>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EffectKind {
    Reverb,
    Delay,
    Eq,
    Compression,
    Saturation,
    Chorus,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MixState {
    pub master_volume_db: f32,
    pub master_pan: f32,
    pub target_lufs: f32,
    pub true_peak_limit: f32,
    pub per_stem: HashMap<String, StemState>,
}

impl Default for MixState {
    fn default() -> Self {
        Self {
            master_volume_db: 0.0,
            master_pan: 0.0,
            target_lufs: -14.0,
            true_peak_limit: -1.0,
            per_stem: HashMap::new(),
        }
    }
}

/// EmotionArc tracks how the song FEELS across its duration.
/// MMIE uses this to judge whether the emotional journey is coherent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmotionArc {
    pub overall_mood: String,
    pub emotional_journey: Vec<(BarNumber, SectionEmotion)>,
    pub climax_position: f32, // 0.0 to 1.0, where is the peak
    pub resolution_present: bool,
}

pub type BarNumber = u16;

impl SongState {
    pub fn new(title: impl Into<String>, key: &str, tempo: u16) -> Self {
        let title = title.into();
        Self {
            description: String::new(),
            title,
            global_key: key.into(),
            global_tempo: tempo,
            sections: vec![],
            mix: MixState::default(),
            emotions: EmotionArc {
                overall_mood: "neutral".into(),
                emotional_journey: vec![],
                climax_position: 0.75,
                resolution_present: true,
            },
        }
    }

    pub fn add_section(
        &mut self,
        name: impl Into<String>,
        kind: SectionKind,
        bars: u8,
        emotion: SectionEmotion,
    ) {
        let name = name.into();
        self.sections.push(Section {
            name: name.clone(),
            kind,
            duration_bars: bars,
            key: self.global_key.clone(),
            tempo: self.global_tempo,
            emotion,
            lyrics: String::new(),
            stems: HashMap::new(),
            melody_notes: vec![],
            chord_progression: vec![],
        });
    }

    pub fn total_bars(&self) -> u16 {
        self.sections.iter().map(|s| s.duration_bars as u16).sum()
    }

    pub fn emotion_at_bar(&self, bar: BarNumber) -> Option<&SectionEmotion> {
        let mut current = 0u16;
        for section in &self.sections {
            let end = current + section.duration_bars as u16;
            if bar >= current && bar < end {
                return Some(&section.emotion);
            }
            current = end;
        }
        None
    }

    pub fn validate_emotion_coherence(&self
    ) -> Vec<String> {
        let mut faults = vec![];
        if self.emotions.climax_position > 0.9 {
            faults.push("Climax too close to end — no room for resolution".into());
        }
        if self.emotions.climax_position < 0.3 {
            faults.push("Climax too early — song peaks and then drags".into());
        }
        if self.emotions.emotional_journey.len() < 2 {
            faults.push("Emotional journey is flat — no arc".into());
        }
        for (i, section) in self.sections.iter().enumerate() {
            if section.emotion.valence.abs() > 0.9 && section.emotion.arousal < 0.3 {
                faults.push(format!(
                    "{}: extreme valence with low arousal feels numb, not expressive",
                    section.name
                ));
            }
        }
        faults
    }
}
