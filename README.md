# RedDirt-Tunes
## The Titan Musical Intelligence — 600B → 5B Distillation with Neural-Spectral Stem Separation

> **RedDirt-Tunes** is the **Titan Musical Intelligence** — a small (5B), specialized music model that uses the same externalized-intelligence architecture as the TITAN coding system (Driver, Inference, Physical Model, MMIE, Stem Separation, NLP/NLU) to compose, separate, edit, write lyrics for, and remaster music.

---

## What RedDirt-Tunes Is

RedDirt-Tunes is a Rust-native, memory-first AI music agent architecture. It lets a **5B-parameter quantized model** match the behavior of a **600B general teacher** in music by moving reasoning, planning, DSP, and linguistic processing outside the neural weights.

The system includes:
- **Neural-Spectral Stem Separation** — isolate any instrument and every vocal from a mix
- **NLP/NLU for Lyrics** — parse mood, intent, and description into structured music parameters and lyric drafts
- **Memory-First Design** — runs on Studio, Live, and Mobile tiers without exceeding strict RAM/VRAM caps
- **MMIE Self-Improvement** — every composition session feeds back into the model

---

## Quick Start (Framework Only — No Weights Yet)

```bash
# Build the system (framework is under 75MB on disk)
cd RedDirt-Tunes
cargo build --release

# Run the bootstrap demo
cargo run --release

# Model backends:
#   1. Place a .gguf model in .reddirt/models/
#   2. Place llama-cli or llama-cli.exe on PATH
#   3. The system auto-discovers and selects the right model by tier
```

---

## Architecture

### Five Pillars

| Pillar | Role | Crate |
|--------|------|-------|
| **Driver** | Mode routing (ARRANGEMENT, STEM_EDIT, GENERATION, REMASTER, LYRIC), task decomposition | `crates/reddirt_driver` |
| **Inference** | 5B music model: generate, edit, compose, remaster | `crates/reddirt_inference` |
| **Physical Model** | On-disk structured memory: stems, sessions, lyrics, rewards | `crates/reddirt_physical_model` |
| **MMIE** | Scoring: render quality, stem clarity, latency, memory, lyrics | `crates/reddirt_mmie` |
| **Stem** | Neural-Spectral Separation: vocals, drums, bass, guitar, piano, other | `crates/reddirt_stem` |

### NLP/NLU Layer
| Component | Role | Crate |
|-----------|------|-------|
| **NLP** | Lyric generation, summarization, mood classification | `crates/reddirt_nlp` |
| **NLU** | Intent parsing (sad → minor key, slow tempo) | `crates/reddirt_nlp` |
| **Capability Profile** | Machine probe: audio interface, RAM, sample rate, tier | `crates/reddirt_capability` |

---

## Memory-First Rules

1. Always quantize by default (Q4/Q2)
2. Hard DSP buffer cap: 64ms@Studio, 128ms@Live, 256ms@Mobile
3. No full mix in RAM: stream stems and patch buffers
4. DSP offloads to Stem crate (not the model)
5. Keep only active stems in RAM
6. Only current session loaded; all music written to `.reddirt/training/trajectories/`
7. MMIE penalizes memory >1.5GB on Mobile and >5GB on Studio

---

## Capability Tiers

| Tier | Stems | Model Mem | Buffer | Real-Time | Separation |
|------|-------|-----------|--------|-----------|------------|
| **Studio** | 64 | 5,000MB | 64ms | Yes | Full |
| **Live** | 16 | 2,500MB | 128ms | Yes | Standard |
| **Mobile** | 4 | 1,000MB | 256ms | No | Light |

---

## Data Mix (RedDirt 5B)

| Category | Ratio |
|----------|-------|
| Composition + Arrangement | 35% |
| Stem Separation + Editing | 25% |
| NLU (mood, key, tempo mapping) | 15% |
| NLP (lyrics, descriptions, prose) | 15% |
| Remaster + Mixing | 10% |

---

## Status

| Component | Status |
|-----------|--------|
| Capability Profile (Studio/Live/Mobile tiers) | ✅ |
| Driver Modes (5 modes) | ✅ |
| Tool Executor schema | 🔄 |
| Stem Separator (stub ready for ONNX/DSP call) | ✅ |
| NLU Intent Parser (mood → key/tempo) | ✅ |
| NLP Lyric Generator (stub) | ✅ |
| MMIE Scoring (render, stem clarity, memory, latency) | ✅ |
| Inference Facade (LlamaCliBackend + MockBackend) | 🔄 |
| Physical Model I/O | ✅ |
| Training Pipeline (Python) | 🔄 |

---

## Binary Footprint

| Build | Size |
|-------|------|
| Debug | ~4 MB |
| **Release** | **~0.16 MB (163 KB)** |

Model weights are external (loaded at runtime) — they do not count toward the project binary.

---

## Project Structure

```
RedDirt-Tunes/
├── Cargo.toml                          # Workspace root
├── src/main.rs                         # Bootstrap demo
├── README.md                           # This file
├── PAPER.md                            # Formal system paper
├── AGENTS.md                           # Agent specs
├── crates/
│   ├── reddirt_capability            # Machine profiler + tier logic
│   ├── reddirt_driver                # Mode-based agent conductor
│   ├── reddirt_inference             # Model facade + generation backend
│   ├── reddirt_physical_model        # On-disk memory schemas + I/O
│   ├── reddirt_mmie                  # Reward scoring + trajectory curation
│   ├── reddirt_stem                  # Neural-Spectral Separation engine
│   └── reddirt_nlp                   # NLU intent + NLP lyric generation
└── training/
    ├── distill.py                    # Dataset builder for 600B → 5B
    ├── train.py                      # PyTorch / PEFT / TRL trainer
    └── prompts.md                    # Music mode prompt templates
```

---

## License

MIT
