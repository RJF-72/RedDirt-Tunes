use reddirt_capability::{CapabilityProfile, Tier};
use reddirt_nlp::{NlpEngine, MusicIntent};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Mode {
    Arrangement,
    StemEdit,
    Generation,
    Remaster,
    Lyric,
    Vocal,   // Sing the lyrics
    Master,  // Radio-ready finishing
}

pub struct Driver {
    pub profile: CapabilityProfile,
    pub mode: Mode,
    pub step_count: usize,
    pub max_steps: usize,
    pub nlp: NlpEngine,
}

impl Driver {
    pub fn new(profile: CapabilityProfile) -> Self {
        let max_steps = match profile.tier {
            Tier::Studio => 20,
            Tier::Live => 12,
            Tier::Mobile => 8,
        };
        Self { profile, mode: Mode::Arrangement, step_count: 0, max_steps, nlp: NlpEngine::new() }
    }

    pub fn classify(&self, request: &str) -> Mode {
        let lower = request.to_lowercase();
        if lower.contains("sing") || lower.contains("vocal track") || lower.contains("singer") {
            Mode::Vocal
        } else if lower.contains("master") || lower.contains("radio ready") || lower.contains("final") || lower.contains("broadcast") {
            Mode::Master
        } else if lower.contains("stem") || lower.contains("separate") || lower.contains("isolation") {
            Mode::StemEdit
        } else if lower.contains("remaster") || lower.contains("mix") {
            Mode::Remaster
        } else if lower.contains("lyric") || lower.contains("words") {
            Mode::Lyric
        } else if lower.contains("generate") || lower.contains("compose") || lower.contains("create") {
            Mode::Generation
        } else {
            Mode::Arrangement
        }
    }

    pub fn build_turn(&self, request: &str) -> Turn {
        let mode = self.classify(request);
        let intent = self.nlp.parse_intent(request);
        Turn {
            mode,
            system_prompt: format!("REDDIRT MUSICAL INTELLIGENCE | Mode: {:?} | Intent: key={} tempo={}", mode, intent.key, intent.tempo),
            task_query: request.into(),
            music_params: intent,
            target_lufs: match self.profile.tier {
                Tier::Studio => Some(-14.0),
                Tier::Live => Some(-16.0),
                Tier::Mobile => Some(-18.0),
            },
        }
    }
}

pub struct Turn {
    pub mode: Mode,
    pub system_prompt: String,
    pub task_query: String,
    pub music_params: MusicIntent,
    pub target_lufs: Option<f32>,
}
