use eframe::{egui, App, Frame, NativeOptions};
use reddirt_capability::CapabilityProfile;
use reddirt_driver::Driver;
use reddirt_inference::InferenceEngine;
use reddirt_nlp::NlpEngine;
use reddirt_vocals::{VocalSynthesizer, VocalTrack, SungPhoneme, VocalParams};
use reddirt_master::{MasteringEngine, MasterSettings, RenderedTrack};
use reddirt_mmie::MmieLoop;
use reddirt_physical_model::{Step, EnvFeedback, AudioOutcome};

pub struct RedDirtApp {
    pub song_title: String,
    pub song_description: String,
    pub song_lyrics: String,
    pub status: String,
    pub profile: CapabilityProfile,
    pub driver: Driver,
    pub inference: InferenceEngine,
    pub mmie: MmieLoop,
}

impl Default for RedDirtApp {
    fn default() -> Self {
        let profile = CapabilityProfile::probe();
        Self {
            song_title: String::with_capacity(50),
            song_description: String::with_capacity(2500),
            song_lyrics: String::with_capacity(5000),
            status: "Ready".into(),
            driver: Driver::new(profile.clone()),
            inference: InferenceEngine::from_profile(profile.clone()),
            mmie: MmieLoop::new(profile.clone()),
            profile,
        }
    }
}

impl App for RedDirtApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut Frame) {
        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading("RedDirt-Tunes — Titan Musical Intelligence");
            ui.separator();

            // Song Title
            ui.horizontal(|ui| {
                ui.label("Song Title:");
                ui.add(egui::TextEdit::singleline(&mut self.song_title).char_limit(50));
            });
            ui.label(format!("{}/50 chars", self.song_title.len()));

            ui.separator();

            // Song Description
            ui.label("Song Description:");
            ui.add(
                egui::TextEdit::multiline(&mut self.song_description)
                    .desired_rows(6)
                    .char_limit(2500),
            );
            ui.label(format!("{}/2500 chars", self.song_description.len()));

            ui.separator();

            // Song Lyrics
            ui.label("Song Lyrics:");
            ui.add(
                egui::TextEdit::multiline(&mut self.song_lyrics)
                    .desired_rows(12)
                    .char_limit(5000),
            );
            ui.label(format!("{}/5000 chars", self.song_lyrics.len()));

            ui.separator();

            // Tier / Status
            ui.horizontal(|ui| {
                ui.label(format!("Tier: {:?}", self.profile.tier));
                ui.label(format!("Status: {}", self.status));
            });

            // Action Buttons
            ui.horizontal(|ui| {
                if ui.button("Compose & Arrange").clicked() {
                    let prompt = format!(
                        "{}\n{}",
                        self.song_title,
                        self.song_description
                    );
                    let turn = self.driver.build_turn(&prompt);
                    self.status = format!("Mode: {:?} | {}"
, turn.mode);
                }
                if ui.button("Synthesize Vocals").clicked() {
                    self.status = "Singing lyrics...".into();
                    let synth = VocalSynthesizer::new();
                    let track = VocalTrack {
                        phonemes: vec![
                            SungPhoneme {
                                text: self.song_lyrics.clone(),
                                note: "A3".into(),
                                params: VocalParams {
                                    pitch_hz: 220.0,
                                    duration_ms: 4000,
                                    velocity: 0.7,
                                    vibrato_rate: 5.5,
                                    vibrato_depth: 0.3,
                                    breathiness: 0.2,
                                    formant_shift: 0.0,
                                },
                            },
                        ],
                        singer_id: "reddirt_default".into(),
                        emotion: "sad".into(),
                    };
                    if let Ok(vocal) = synth.render(&track) {
                        self.status = format!(
                            "Vocal rendered: {}ms at {}Hz",
                            vocal.duration_ms, vocal.sample_rate
                        );
                    } else {
                        self.status = "Vocal render failed".into();
                    }
                }
                if ui.button("Radio-Ready Master").clicked() {
                    self.status = "Mastering for broadcast...".into();
                    let master = MasteringEngine::new();
                    let track = RenderedTrack {
                        samples_l: vec![],
                        samples_r: vec![],
                        sample_rate: 48000,
                    };
                    if let Ok(_) = master.master(&track, &MasterSettings::default()) {
                        self.status = "Mastering complete (-14 LUFS)".into();
                    }
                }
                if ui.button("Full Pipeline").clicked() {
                    self.status = "Compose → Sing → Master...".into();
                }
            });

            ui.separator();

            // Progress / Output
            egui::ScrollArea::vertical().show(ui, |ui| {
                ui.label(format!("Output Log:\n{}", self.status));
            });
        });
    }
}

fn main() {
    let options = NativeOptions::default();
    eframe::run_native(
        "RedDirt-Tunes",
        options,
        Box::new(|_cc| Ok(Box::new(RedDirtApp::default()))),
    ).unwrap();
}
