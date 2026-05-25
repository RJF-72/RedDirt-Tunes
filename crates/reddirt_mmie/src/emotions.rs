// MMIE as Emotional Cortex
// Scores whether the song FEELS right.

use reddirt_physical_model::song_state::{SongState, SectionEmotion};

#[derive(Debug, Clone)]
pub struct EmotionalRewards {
    pub coherence: f64,           // do sections flow emotionally?
    pub contrast: f64,            // is there tension/release?
    pub climax_placement: f64,    // is the peak at the right spot?
    pub vocal_expression: f64,    // does the vocalist match the section emotion?
    pub lyrical_alignment: f64, // do the lyrics match the music's emotion?
    pub resolution: f64,          // does the song land or leave hanging?
    pub total: f64,
}

pub struct EmotionalCortex;

impl EmotionalCortex {
    pub fn new() -> Self {
        Self
    }

    pub fn score_song(&self,
        song: &SongState,
        vocal_expression_per_section: &[(usize, f64)], // (section_idx, 0-1)
        lyrical_mood_match: f64, // 0-1
    ) -> EmotionalRewards {
        let faults = song.validate_emotion_coherence();

        // Coherence: adjacent sections should not have violent jumps
        let mut coherence = 1.0f64;
        for w in song.sections.windows(2) {
            let a = &w[0].emotion;
            let b = &w[1].emotion;
            // Penalize 180-degree turns
            let delta = ((a.valence - b.valence).abs() + (a.arousal - b.arousal).abs()) as f64;
            if delta > 1.5 {
                coherence -= 0.2;
            }
        }
        coherence = coherence.clamp(0.0, 1.0);

        // Contrast: some tension and release, not flat
        let emotions: Vec<&SectionEmotion> = song.sections.iter().map(|s| &s.emotion).collect();
        let avg_valence: f32 = emotions.iter().map(|e| e.valence).sum::<f32>() / emotions.len().max(1) as f32;
        let avg_arousal: f32 = emotions.iter().map(|e| e.arousal).sum::<f32>() / emotions.len().max(1) as f32;
        let contrast = ((avg_valence.abs() + avg_arousal) as f64).clamp(0.0, 1.0);

        // Climax placement: should be at 65-85%
        let climax_pos = song.emotions.climax_position as f64;
        let climax_score = if climax_pos >= 0.65 && climax_pos <= 0.85 {
            1.0
        } else {
            1.0 - (climax_pos - 0.75).abs() * 2.0
        }.clamp(0.0, 1.0);

        // Vocal expression average
        let vocal_avg: f64 = if !vocal_expression_per_section.is_empty() {
            vocal_expression_per_section.iter().map(|(_, s)| s).sum::<f64>() / vocal_expression_per_section.len() as f64
        } else {
            0.5
        };

        // Resolution
        let resolution = if song.emotions.resolution_present { 1.0 } else { 0.2 };

        // Penalty from faults
        let fault_penalty = (faults.len() as f64 * 0.1).clamp(0.0, 1.0);

        let total = coherence + contrast + climax_score + vocal_avg + lyrical_mood_match + resolution - fault_penalty;
        let total = (total / 6.0).clamp(0.0, 1.0);

        EmotionalRewards {
            coherence,
            contrast,
            climax_placement: climax_score,
            vocal_expression: vocal_avg,
            lyrical_alignment: lyrical_mood_match,
            resolution,
            total,
        }
    }

    /// What should we inject into the system prompt to guide the model emotionally?
    pub fn emotional_guidance(song: &SongState) -> String {
        format!(
            "This song is '{}' — key of {} at {} BPM.\n\
             Overall mood: {}.\n\
             Climax should land near {:.0}% of the song.\n\
             Ensure resolution is {}.\n\
             Emotional arc should move from {} arousal / {} valence to {} arousal / {} valence.",
            song.title,
            song.global_key,
            song.global_tempo,
            song.emotions.overall_mood,
            song.emotions.climax_position * 100.0,
            if song.emotions.resolution_present {
                "present"
            } else {
                "optional / unresolved"
            },
            if let Some(s) = song.sections.first() { s.emotion.arousal } else { 0.5 },
            if let Some(s) = song.sections.first() { s.emotion.valence } else { 0.0 },
            if let Some(s) = song.sections.last()  { s.emotion.arousal } else { 0.5 },
            if let Some(s) = song.sections.last()  { s.emotion.valence } else { 0.0 },
        )
    }
}
