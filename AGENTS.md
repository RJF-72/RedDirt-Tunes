# RedDirt-Tunes Architecture Document
## The Titan Musical Intelligence: 600B → 5B with Externalized Intelligence

### Philosophy

RedDirt-Tunes applies the TITAN architecture pattern (Driver + Inference + Physical Model + MMIE) from code to music. The 5B student is not a "shrunken 600B music model." It is a re-architected system where **the model generates the language of music**, and **the system provides the intelligence of composition, separation, lyrics, and remastering**.

---

## Six Pillars

### 1. The Driver (Creative Cortex)
Routes user requests into strict music modes:

- **ARRANGEMENT** — structure, sections, instrumentation choices
- **STEM_EDIT** — isolate, replace, or mute any instrument
- **GENERATION** — compose a full piece from mood/key/tempo
- **REMASTER** — EQ, compression, loudness matching
- **LYRIC** — generate matching text/vocals

### 2. The Inference Engine (5B Audio Language Model)
Trained multi-task:
- 35% composition + arrangement
- 25% stem separation
- 15% NLU (mood → key/tempo)
- 15% NLP (lyrics, descriptions)
- 10% remaster + mixing

Quantization by tier:
- Studio → Q5 (5GB)
- Live → Q4 (2.5GB)
- Mobile → Q2 (1GB)

### 3. Neural-Spectral Stem Separation
Separates any mix into vocals, drums, bass, guitar, piano, and other.
Runs in `reddirt_stem` (not inside the model) to stay memory-safe.

### 4. NLU / NLP Cortex
- **NLU** parses natural language descriptions ("sad acoustic ballad about rain") into music metadata: key, tempo, time signature, instrumentation.
- **NLP** generates lyrics and track notes.

### 5. Physical Model (Memory + Session Engine)
Stores on disk:
- Sessions (stems, mix, lyrics, rendered output)
- Training trajectories (model generations, stems, rewards)
- Mix history and patches

### 6. MMIE (Creative Scoring Engine)
Rewards:
- Render pass/fail
- Stem clarity (≥4 stems = 1.0)
- Memory under target
- Latency under buffer cap
- NLP quality (lyric coherence, rhyme, story alignment)

---

## Distillation Pipeline (600B → 5B)

1. **Teacher Runs**: 600B general music model under driver → record trajectories
2. **Dataset Build**: Extract SFT pairs (mood/key/tempo → generation, stem commands, lyric output)
3. **Weighted SFT**: Heavy loss on stem JSON and arrangement blocks; lower on prose explanations
4. **Gap Filling**: Where the 5B fails (e.g., complex polyrhythms), generate more 600B data and re-distill
5. **MMIE Self-Improvement**: Turn off teacher. Let 5B run sessions. Score with MMIE. Periodically retrain on top trajectories.

---

## File Map

- `crates/reddirt_capability` — Audio profiler + Studio/Live/Mobile tier logic
- `crates/reddirt_driver` — Mode-based creative conductor
- `crates/reddirt_physical_model` — On-disk session schemas + I/O
- `crates/reddirt_mmie` — Reward scoring + session curation
- `crates/reddirt_inference` — Model facade + generation backend
- `crates/reddirt_stem` — Neural-Spectral Separation engine
- `crates/reddirt_nlp` — NLU intent + NLP lyric generation
- `training/distill.py` — Dataset builder for distillation
- `training/train.py` — PyTorch / PEFT / TRL trainer
- `training/prompts.md` — Music mode prompt templates
