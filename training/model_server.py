#!/usr/bin/env python3
"""
RedDirt-Tunes Instrument Generation Server
Port: 8765

Generates real multi-track instrumental music using procedural synthesis:
- Subtractive bass (sawtooth + resonant LPF)
- Additive chords/pads (sum of sine waves, minor/major voicings)
- FM lead/arpeggio
- Drum kit (kick, snare, hi-hat from pure synthesis)

Takes text prompts like "sad acoustic ballad about rain, key A minor, tempo 65"
and produces actual audio files. No ML models required.

Usage:
    python training/model_server.py --host 127.0.0.1 --port 8765
"""
import json
import sys
import argparse
import hashlib
import math
import random
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("[model] ERROR: Flask not installed. Run: pip install flask")
    sys.exit(1)

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter, butter

app = Flask("RedDirt-Instrument")

SR = 48000

# ── Music Theory ─────────────────────────────────────────────────
SCALES = {
    "C":  ["C", "D", "E", "F", "G", "A", "B"],
    "Am": ["A", "B", "C", "D", "E", "F", "G"],
    "Em": ["E", "F#", "G", "A", "B", "C", "D"],
    "Dm": ["D", "E", "F", "G", "A", "Bb", "C"],
    "Gm": ["G", "A", "Bb", "C", "D", "Eb", "F"],
    "F":  ["F", "G", "A", "Bb", "C", "D", "E"],
    "G":  ["G", "A", "B", "C", "D", "E", "F#"],
    "D":  ["D", "E", "F#", "G", "A", "B", "C#"],
}

NOTE_TO_MIDI = {
    'C': 60, 'C#': 61, 'Db': 61, 'D': 62, 'D#': 63, 'Eb': 63,
    'E': 64, 'F': 65, 'F#': 66, 'Gb': 66, 'G': 67, 'G#': 68,
    'Ab': 68, 'A': 69, 'A#': 70, 'Bb': 70, 'B': 71,
}

CHORD_SHAPES = {
    "major": [0, 4, 7],
    "minor": [0, 3, 7],
    "sus2":  [0, 2, 7],
    "sus4":  [0, 5, 7],
    "dim":   [0, 3, 6],
    "maj7":  [0, 4, 7, 11],
    "m7":    [0, 3, 7, 10],
}

@dataclass
class SongParams:
    key: str = "C"
    tempo_bpm: float = 120.0
    mood: str = "neutral"
    duration_sec: float = 10.0
    bars: int = 8

# ── Synthesis Primitives ───────────────────────────────────────

def midi_to_hz(midi: int) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))

def hz_to_phase_increment(hz: float, sr: int = SR) -> float:
    return 2.0 * math.pi * hz / sr

def note_to_hz(note: str, octave: int = 4) -> float:
    base = NOTE_TO_MIDI.get(note, 60)
    midi = base + (octave - 4) * 12
    return midi_to_hz(midi)

def _adsr_env(samples: int, attack_pct=0.05, decay_pct=0.1,
              sustain_level=0.7, release_pct=0.2) -> np.ndarray:
    """ADSR envelope scaled to sample length."""
    env = np.zeros(samples)
    attack = int(samples * attack_pct)
    decay = int(samples * decay_pct)
    release = int(samples * release_pct)
    sustain = samples - attack - decay - release
    if sustain < 0:
        sustain = 0
        attack = samples // 3
        decay = samples // 3
        release = samples - attack - decay

    env[:attack] = np.linspace(0.0, 1.0, attack)
    if decay > 0:
        env[attack:attack + decay] = np.linspace(1.0, sustain_level, decay)
    env[attack + decay:attack + decay + sustain] = sustain_level
    if release > 0:
        env[-release:] = np.linspace(sustain_level, 0.0, release)
    return env

def _subtractive_bass(freq: float, duration_sec: float,
                      sr: int = SR, vel: float = 1.0) -> np.ndarray:
    """Sawtooth through resonant low-pass = warm bass."""
    samples = int(duration_sec * sr)
    t = np.arange(samples) / sr
    saw = np.zeros(samples)
    n_harm = min(20, int(sr / (2.0 * freq)))
    phase = 2.0 * math.pi * freq * t
    for h in range(1, n_harm + 1):
        saw += ((-1.0) ** (h + 1)) / h * np.sin(phase * h)
    saw *= 0.3

    b, a = butter(2, min(freq * 8, sr / 2 - 100) / (sr / 2), btype='low')
    filtered = lfilter(b, a, saw)
    env = _adsr_env(samples, attack_pct=0.02, decay_pct=0.15,
                    sustain_level=0.8, release_pct=0.1)
    return filtered * env * vel

def _additive_pad(chord_midi: List[int], duration_sec: float,
                  sr: int = SR, vel: float = 0.6) -> np.ndarray:
    """Sum of sine waves with slight detune = lush pad."""
    samples = int(duration_sec * sr)
    pad = np.zeros(samples)
    for m in chord_midi:
        f = midi_to_hz(m)
        t = np.arange(samples) / sr
        # Slight random detune per partial
        detune = 1.0 + (random.random() - 0.5) * 0.003
        pad += np.sin(2.0 * math.pi * f * detune * t)
        # Add upper partials more quietly
        pad += 0.3 * np.sin(2.0 * math.pi * f * 2.0 * detune * t)
        pad += 0.15 * np.sin(2.0 * math.pi * f * 3.0 * detune * t)
    pad /= max(len(chord_midi), 1)
    # Low-pass to soften
    b, a = butter(2, 3000 / (sr / 2), btype='low')
    pad = lfilter(b, a, pad)
    env = _adsr_env(samples, attack_pct=0.3, decay_pct=0.2,
                    sustain_level=0.5, release_pct=0.3)
    return pad * env * vel

def _fm_lead(freq: float, duration_sec: float,
             mod_ratio: float = 2.0, mod_depth: float = 300.0,
             sr: int = SR, vel: float = 0.7) -> np.ndarray:
    """FM synthesis: carrier + modulator = bell-like / glassy lead."""
    samples = int(duration_sec * sr)
    t = np.arange(samples) / sr
    mod_freq = freq * mod_ratio
    mod_signal = mod_depth * np.sin(2.0 * math.pi * mod_freq * t)
    phase = np.cumsum(2.0 * math.pi * (freq + mod_signal) / sr)
    carrier = np.sin(phase)
    env = _adsr_env(samples, attack_pct=0.01, decay_pct=0.4,
                    sustain_level=0.3, release_pct=0.15)
    return carrier * env * vel

def _kick(vel: float = 1.0, sr: int = SR) -> np.ndarray:
    """Kick drum = sine sweep from high to low."""
    samples = int(0.15 * sr)
    t = np.arange(samples) / sr
    start_freq = 150.0
    end_freq = 40.0
    freq = start_freq * np.exp(t * np.log(end_freq / start_freq) / t[-1])
    phase = np.cumsum(2.0 * math.pi * freq / sr)
    kick = np.sin(phase)
    env = np.exp(-t / 0.08)
    return kick * env * vel

def _snare(vel: float = 0.6, sr: int = SR) -> np.ndarray:
    """Snare = tone + noise, filtered."""
    tone_samples = int(0.1 * sr)
    noise_samples = int(0.15 * sr)
    t_tone = np.arange(tone_samples) / sr
    tone = np.sin(2.0 * math.pi * 200.0 * t_tone) * np.exp(-t_tone / 0.05)
    noise = np.random.randn(noise_samples) * np.exp(-np.arange(noise_samples) / (sr * 0.08))
    b, a = butter(2, [200, 6000], btype='band', fs=sr)
    noise = lfilter(b, a, noise)
    out = np.zeros(max(tone_samples, noise_samples))
    out[:tone_samples] += tone * 0.6
    out[:noise_samples] += noise * 0.8
    return out * vel

def _hihat(vel: float = 0.4, sr: int = SR) -> np.ndarray:
    """Hi-hat = short filtered noise burst."""
    samples = int(0.05 * sr)
    noise = np.random.randn(samples)
    b, a = butter(4, 8000 / (sr / 2), btype='high')
    out = lfilter(b, a, noise)
    env = np.exp(-np.arange(samples) / (sr * 0.02))
    return out * env * vel

# ── Arrangement Engine ───────────────────────────────────────────

def parse_params(prompt: str, duration: int, key: str, tempo: int) -> SongParams:
    mood = "neutral"
    if any(w in prompt.lower() for w in ["sad", "melancholy", "rain", "tear"]):
        mood = "sad"
    elif any(w in prompt.lower() for w in ["happy", "joy", "bright", "sun"]):
        mood = "happy"
    elif any(w in prompt.lower() for w in ["angry", "rage", "dark", "heavy"]):
        mood = "dark"

    bars = max(2, int(duration / (60.0 / tempo) / 4))
    return SongParams(key=key, tempo_bpm=float(tempo), mood=mood,
                      duration_sec=float(duration), bars=bars)

def build_chord_progression(params: SongParams) -> List[Tuple[str, str]]:
    """Build a chord progression from the key and mood."""
    scale = SCALES.get(params.key, SCALES["C"])
    # Roman numerals mapped to scale degrees
    if params.mood == "sad":
        # vi - IV - I - V in minor context, or i - VII - VI - V
        if "m" in params.key:
            prog = [scale[0], scale[6], scale[5], scale[4]]
            types = ["minor", "major", "minor", "major"]
        else:
            prog = [scale[5], scale[3], scale[0], scale[1]]
            types = ["minor", "major", "major", "minor"]
    elif params.mood == "happy":
        prog = [scale[0], scale[5], scale[3], scale[4]]
        types = ["major", "minor", "major", "major"]
    elif params.mood == "dark":
        prog = [scale[0], scale[2], scale[3], scale[5]]
        types = ["minor", "dim", "major", "minor"]
    else:
        prog = [scale[0], scale[3], scale[4], scale[0]]
        types = ["major", "major", "major", "major"]
    return list(zip(prog, types))

def generate_full_track(params: SongParams, sr: int = SR) -> np.ndarray:
    """Compose and render a full multi-instrument track."""
    total_samples = int(params.duration_sec * sr)
    beat_dur = 60.0 / params.tempo_bpm
    bar_samples = int(4 * beat_dur * sr)

    bass = np.zeros(total_samples)
    pad = np.zeros(total_samples)
    lead = np.zeros(total_samples)
    drums = np.zeros(total_samples)

    chords = build_chord_progression(params)
    num_chords = len(chords)

    for bar in range(params.bars):
        bar_start = bar * bar_samples
        if bar_start >= total_samples:
            break

        chord_note, chord_type = chords[bar % num_chords]
        root_midi = NOTE_TO_MIDI.get(chord_note, 60)
        intervals = CHORD_SHAPES.get(chord_type, CHORD_SHAPES["major"])
        chord_midi = [root_midi + i for i in intervals]

        # Bass plays root on beat 1 and beat 3
        for beat in [0, 2]:
            b_start = bar_start + int(beat * beat_dur * sr)
            b_dur = beat_dur * 0.9
            if b_start + int(b_dur * sr) > total_samples:
                continue
            bass_note = bass_slice = _subtractive_bass(midi_to_hz(root_midi - 24), b_dur, sr, vel=0.9)
            end_idx = min(b_start + len(bass_note), total_samples)
            bass[b_start:end_idx] += bass_note[:end_idx - b_start]

        # Pad plays full chord for the bar
        pad_start = bar_start
        pad_dur = min(4 * beat_dur, (total_samples - pad_start) / sr)
        pad_note = _additive_pad(chord_midi, pad_dur, sr, vel=0.5)
        end_idx = min(pad_start + len(pad_note), total_samples)
        pad[pad_start:end_idx] += pad_note[:end_idx - pad_start]

        # Lead: simple arpeggio on beats
        if params.mood != "sad" or bar % 2 == 0:  # sad = sparser lead
            arp_notes = chord_midi[:3]
            for i, note in enumerate(arp_notes):
                l_start = bar_start + int((i + 0.5) * beat_dur * sr)
                if l_start >= total_samples:
                    continue
                l_dur = beat_dur * 0.45
                lead_note = _fm_lead(midi_to_hz(note + 12), l_dur, mod_ratio=1.5, mod_depth=250.0, sr=sr, vel=0.5)
                end_idx = min(l_start + len(lead_note), total_samples)
                lead[l_start:end_idx] += lead_note[:end_idx - l_start]

        # Drums: kick on 1, snare on 3, hihat on all
        for beat in range(4):
            d_start = bar_start + int(beat * beat_dur * sr)
            if d_start >= total_samples:
                continue
            if beat == 0:
                k = _kick(vel=1.0, sr=sr)
                end_idx = min(d_start + len(k), total_samples)
                drums[d_start:end_idx] += k[:end_idx - d_start]
            elif beat == 2:
                s = _snare(vel=0.7, sr=sr)
                end_idx = min(d_start + len(s), total_samples)
                drums[d_start:end_idx] += s[:end_idx - d_start]
            # Hihat on every beat
            h = _hihat(vel=0.35 if beat % 2 == 0 else 0.25, sr=sr)
            end_idx = min(d_start + len(h), total_samples)
            drums[d_start:end_idx] += h[:end_idx - d_start]

    # Mix with sidechain-ish ducking on pad from kick
    mix = bass * 0.9 + pad * 0.5 + lead * 0.4 + drums * 0.85

    # Normalize without hard clipping
    peak = np.max(np.abs(mix))
    if peak > 0.001:
        mix /= peak
        mix *= 0.95

    return mix.astype(np.float32)


# ── Server ───────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "backend": "procedural-synth",
                    "model": "additive+subtractive+fm", "device": "CPU"})


@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"status": "error", "message": "No JSON body"}), 400

        prompt = data.get("prompt", "C major song")
        duration = data.get("duration", 10)
        key = data.get("key", "C")
        tempo = data.get("tempo", 120)
        mode = data.get("mode", "GENERATION")
        output_dir = Path(data.get("output_dir", ".reddirt/output"))
        output_dir.mkdir(parents=True, exist_ok=True)

        params = parse_params(prompt, duration, key, tempo)
        print(f"[model] Generating: {prompt} | {key} | {tempo}BPM | {duration}s | mood={params.mood}")

        audio = generate_full_track(params)

        hash_id = hashlib.md5(prompt.encode()).hexdigest()[:8]
        out_path = output_dir / f"generated_{hash_id}.wav"
        wavfile.write(str(out_path), SR, audio)

        return jsonify({
            "status": "ok",
            "audio_path": str(out_path),
            "backend": "procedural-synth",
            "metadata": {
                "prompt": prompt,
                "duration": duration,
                "key": key,
                "tempo": tempo,
                "mode": mode,
                "mood": params.mood,
                "bars": params.bars,
                "sample_rate": SR,
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


def main():
    parser = argparse.ArgumentParser(description="RedDirt-Tunes Instrument Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    print(f"[model] Instrument Synthesis Server on http://{args.host}:{args.port}")
    print(f"[model] Generates real music from text using additive+subtractive+FM synthesis.")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
