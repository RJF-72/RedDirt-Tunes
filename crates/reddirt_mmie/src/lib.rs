// RedDirt MMIE — The Emotional Cortex
// Scores whether the song FEELS right, not just whether it compiles.

use reddirt_physical_model::{Step, Rewards};
use reddirt_physical_model::song_state::{SongState, SectionEmotion};
use reddirt_capability::CapabilityProfile;

pub mod emotions;

pub struct MmieLoop {
    profile: CapabilityProfile,
}

impl MmieLoop {
    pub fn new(profile: CapabilityProfile) -> Self {
        Self { profile }
    }

    /// Score a single engineering step (render, latency, memory).
    pub fn score_step(
        &self,
        step: &Step,
        num_steps: usize,
        stem_count: usize,
        render_ok: bool,
        nlp_quality: f64,
    ) -> Rewards {
        let render_r = if render_ok { 1.0 } else { 0.0 };
        let steps_penalty = -(num_steps.saturating_sub(3) as f64 * 0.1);
        let mem_penalty = if step.env_feedback.memory_used_mb > self.profile.limits.max_model_mem_mb {
            -0.5
        } else { 0.0 };
        let stem_r = if stem_count >= 4 { 1.0 } else { 0.5 };
        let total = (render_r + steps_penalty + mem_penalty + stem_r + nlp_quality).clamp(-3.0, 3.0);
        Rewards {
            render: render_r,
            latency_penalty: steps_penalty,
            memory_penalty: mem_penalty,
            stem_clarity: stem_r,
            nlp_quality,
            total,
        }
    }

    /// Score the emotional arc of an entire song.
    /// This is what separates music MMIE from coding MMIE.
    pub fn score_emotion(
        &self,
        song: &SongState,
        vocal_expression_per_section: &[(usize, f64)],
        lyrical_mood_match: f64,
    ) -> EmotionalRewards {
        let faults = song.validate_emotion_coherence();

        // Coherence: adjacent sections should not have violent emotional jumps
        let mut coherence = 1.0f64;
        for w in song.sections.windows(2) {
            let a = &w[0].emotion;
            let b = &w[1].emotion;
            let delta = ((a.valence - b.valence).abs() + (a.arousal - b.arousal).abs()) as f64;
            if delta > 1.5 {
                coherence -= 0.2;
            }
        }
        coherence = coherence.clamp(0.0, 1.0);

        // Contrast: is there tension and release, or is the song flat?
        let emotions: Vec<&SectionEmotion> = song.sections.iter().map(|s| &s.emotion).collect();
        let avg_valence: f32 = emotions.iter().map(|e| e.valence).sum::<f32>() / emotions.len().max(1) as f32;
        let avg_arousal: f32 = emotions.iter().map(|e| e.arousal).sum::<f32>() / emotions.len().max(1) as f32;
        let contrast = ((avg_valence.abs() + avg_arousal) as f64).clamp(0.0, 1.0);

        // Climax placement: should land at 65-85% for maximum impact
        let climax_pos = song.emotions.climax_position as f64;
        let climax_score = if climax_pos >= 0.65 && climax_pos <= 0.85 {
            1.0
        } else {
            1.0 - (climax_pos - 0.75).abs() * 2.0
        }.clamp(0.0, 1.0);

        // Vocal expression: singer must match each section's emotion
        let vocal_avg: f64 = if !vocal_expression_per_section.is_empty() {
            vocal_expression_per_section.iter().map(|(_, s)| s).sum::<f64>() / vocal_expression_per_section.len() as f64
        } else {
            0.5
        };

        // Resolution: does the song land, or hang unresolved?
        let resolution = if song.emotions.resolution_present { 1.0 } else { 0.2 };

        // Fault penalty from logical errors
        let fault_penalty = (faults.len() as f64 * 0.1).clamp(0.0, 1.0);

        let total = (coherence + contrast + climax_score + vocal_avg + lyrical_mood_match + resolution) / 6.0 - fault_penalty;
        let total = total.clamp(0.0, 1.0);

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

    /// Generate emotional guidance for the model.
    pub fn emotional_guidance(song: &SongState) -> String {
        format!(
            "This song is '{}' — key of {} at {} BPM.\n\
             Overall mood: {}.\n\
             Climax should land near {:.0}% of the song.\n\
             Resolution: {}.\n\
             Arc: {} arousal / {} valence → {} arousal / {} valence.",
            song.title,
            song.global_key,
            song.global_tempo,
            song.emotions.overall_mood,
            song.emotions.climax_position * 100.0,
            if song.emotions.resolution_present { "present" } else { "unresolved" },
            song.sections.first().map(|s| s.emotion.arousal).unwrap_or(0.5),
            song.sections.first().map(|s| s.emotion.valence).unwrap_or(0.0),
            song.sections.last().map(|s| s.emotion.arousal).unwrap_or(0.5),
            song.sections.last().map(|s| s.emotion.valence).unwrap_or(0.0),
        )
    }
}

#[derive(Debug, Clone)]
pub struct EmotionalRewards {
    pub coherence: f64,
    pub contrast: f64,
    pub climax_placement: f64,
    pub vocal_expression: f64,
    pub lyrical_alignment: f64,
    pub resolution: f64,
    pub total: f64,
}