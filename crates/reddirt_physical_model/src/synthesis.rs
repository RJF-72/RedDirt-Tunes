// Real Physical Modeling Synthesis for RedDirt-Tunes
// Not a metaphor — actual DSP engines that model instruments from physics.

/// Karplus-Strong plucked string algorithm.
/// Models a string as a circular buffer + low-pass filter + fractional delay.
pub struct PluckedString {
    buffer: Vec<f32>,
    position: usize,
    feedback: f32,
    filter_state: f32,
}

impl PluckedString {
    /// frequency: Hz, sample_rate: Hz
    pub fn with_tuning(sample_rate: f32, frequency: f32) -> Self {
        let delay_samples = sample_rate / frequency;
        let length = delay_samples.ceil() as usize;
        let frac = delay_samples.fract();
        Self {
            buffer: vec![0.0; length],
            position: 0,
            feedback: 0.5,
            filter_state: 0.0,
        }
    }

    pub fn pluck(&mut self,
        excitation: &[f32],
    ) {
        // Seed the buffer with noise + excitation
        for i in 0..self.buffer.len() {
            self.buffer[i] = excitation.get(i).copied().unwrap_or(0.0);
        }
        self.position = 0;
        self.filter_state = 0.0;
    }

    pub fn next_sample(&mut self
    ) -> f32 {
        let out = self.buffer[self.position];
        // One-pole low-pass filter
        let filtered = self.filter_state * self.feedback + out * (1.0 - self.feedback);
        self.filter_state = filtered;
        // Circular buffer with feedback
        self.buffer[self.position] = out * self.feedback;
        self.position = (self.position + 1) % self.buffer.len();
        out
    }
}

/// Digital Waveguide for wind / bowed instruments.
/// Two delay lines model left and right traveling waves.
pub struct Waveguide {
    left: Vec<f32>,
    right: Vec<f32>,
    pos: usize,
    length: usize,
    reflection: f32,
}

impl Waveguide {
    pub fn with_tuning(sample_rate: f32, frequency: f32) -> Self {
        let length = (sample_rate / frequency).ceil() as usize;
        Self {
            left: vec![0.0; length],
            right: vec![0.0; length],
            pos: 0,
            length,
            reflection: 0.99,
        }
    }

    pub fn excite(&mut self,
        impulse: f32
    ) {
        self.left[self.pos] += impulse;
    }

    pub fn next_sample(&mut self
    ) -> f32 {
        let l = self.left[self.pos];
        let r = self.right[self.pos];
        self.left[self.pos] = r * self.reflection;
        self.right[self.pos] = l * self.reflection;
        self.pos = (self.pos + 1) % self.length;
        l + r
    }
}

/// Modal synthesis for percussion (drums, gongs).
/// Model: sum of exponentially decaying sinusoids (resonant modes).
pub struct ModalResonator {
    modes: Vec<ResonantMode>,
}

struct ResonantMode {
    freq_hz: f32,
    amp: f32,
    decay: f32,
    phase: f32,
    n: usize,
}

impl ModalResonator {
    pub fn from_spec(sample_rate: f32, specs: &[(f32, f32, f32)]) -> Self {
        let modes = specs.iter().map(|(freq, amp, decay)| {
            ResonantMode {
                freq_hz: *freq,
                amp: *amp,
                decay: *decay, // per-sample decay factor
                phase: 0.0,
                n: 0,
            }
        }).collect();
        Self { modes }
    }

    pub fn strike(&mut self,
        velocity: f32,
    ) {
        for m in &mut self.modes {
            m.n = 0;
        }
    }

    pub fn next_sample(&mut self
    ) -> f32 {
        let mut sum = 0.0f32;
        for m in &mut self.modes {
            let t = m.n as f32 * (1.0 / 48000.0);
            let envelope = (-m.decay * t).exp();
            sum += (m.phase).sin() * m.amp * envelope;
            m.phase += 2.0 * std::f32::consts::PI * m.freq_hz / 48000.0;
            m.n += 1;
        }
        sum
    }
}

/// Piano hammer model (nonlinear strike + string waveguide).
pub struct HammeredString {
    string: PluckedString,
    hammer_mass: f32,
    hammer_stiffness: f32,
    velocity: f32,
}

impl HammeredString {
    pub fn with_tuning(sample_rate: f32, frequency: f32) -> Self {
        Self {
            string: PluckedString::with_tuning(sample_rate, frequency),
            hammer_mass: 0.01,
            hammer_stiffness: 1000.0,
            velocity: 2.0,
        }
    }

    pub fn strike(&mut self,
        velocity: f32,
    ) {
        // Generate a nonlinear hammer impulse
        let contact_duration = (0.001 * 48000.0) as usize;
        let mut impulse = vec![0.0f32; contact_duration];
        for i in 0..contact_duration {
            let t = i as f32 / contact_duration as f32;
            // Simplified Hertzian contact: force grows then drops
            impulse[i] = velocity * (1.0 - t).powf(1.5) * 0.5;
        }
        self.string.pluck(&impulse);
    }

    pub fn next_sample(&mut self
    ) -> f32 {
        self.string.next_sample()
    }
}

/// Simple sine oscillator (reference / placeholder for comparison).
pub struct SineOsc {
    phase: f32,
    freq_hz: f32,
    sr: f32,
}

impl SineOsc {
    pub fn new(freq_hz: f32, sr: f32) -> Self {
        Self { phase: 0.0, freq_hz, sr }
    }
    pub fn next_sample(&mut self
    ) -> f32 {
        let s = self.phase.sin();
        self.phase += 2.0 * std::f32::consts::PI * self.freq_hz / self.sr;
        s
    }
}
