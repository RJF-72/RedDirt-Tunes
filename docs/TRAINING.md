# RedDirt-Tunes Training Pipeline
## Distilling 600B → 5B for Symbolic Music Generation

### Philosophy

The 600B teacher model handles the full creative pipeline. The 5B student only needs to **speak music** — output notes, chords, arrangements, lyrics, and mix parameters. The Driver, MMIE, and Physical Model do the heavy lifting.

### Data Schema for Music Generation

Each step in a trajectory is a structured prompt → response pair:

```json
{
  "system": "RedDirt-Tunes | Mode: ARRANGEMENT | Key: Am | Tempo: 65",
  "input": "Sad acoustic ballad, rain imagery, sparse verses, swelling chorus",
  "output": {
    "title": "Rain Song",
    "key": "Am",
    "tempo": 65,
    "climax_position": 0.72,
    "sections": [...]
  },
  "meta": {
    "mode": "ARRANGEMENT",
    "weight": 1.5
  }
}
```

### Distillation Mix (for 5B training)

| Category | Ratio | Loss Weight | Notes |
|----------|-------|-------------|-------|
| Arrangement / Composition | 35% | 1.5 | Song structure, keys, sections |
| Chords / Progressions | 25% | 2.0 | JSON chord sequences |
| Melody / Notes | 15% | 2.5 | MIDI note tokens |
| Lyrics / NLP | 15% | 1.0 | Text generation |
| Stem / Mix Parameters | 10% | 0.5 | Faders, pan, FX |

### Stages

**Stage 1 — Teacher Runs (600B)**
- Run 600B model under RedDirt driver
- Record every arrangement, chord, melody, lyric, stem, mix output
- Tag with emotion scores from MMIE
- Store in `.reddirt/training/trajectories/`

**Stage 2 — Distillation Dataset**
- Extract SFT pairs from top trajectories (reward ≥ threshold)
- Weight by category
- Validate JSON syntax of all music outputs
- Save as JSONL

**Stage 3 — Weighted SFT on 5B**
- Start with RedPajama-INCITE-5B or similar general base
- LoRA with r=128, alpha=256, 4-bit quantization for training
- Higher weight on chord/melody JSON, lower on lyrics
- 3 epochs, FP16

**Stage 4 — Export to GGUF**
- Merge LoRA weights into base model
- Quantize per tier:
  - Studio: Q5_K_M (~3.5 GB)
  - Live: Q4_K_M (~2.9 GB)
  - Mobile: Q3_K_M (~2.2 GB) or Q2 (~1.7 GB)

**Stage 5 — Gap Evaluation**
- Run 5B student on hold-out songs
- Evaluate using:
  - Chord progression coherence (correct voice leading)
  - Key stability (does it change key unexpectedly?)
  - Climax placement accuracy
  - Lyrics matching mood (manual or BLEU vs teacher)
- Identify weak areas, generate more 600B teacher data there

**Stage 6 — MMIE Self-Improvement**
- Turn off 600B teacher
- Let 5B run standalone for real users
- MMIE scores every session emotionally and technically
- Top 20% of trajectories → scheduled retraining batch
- Run SFT, export new GGUF, replace model

### How to Run

```bash
# Step 0: Setup environment
conda create -n reddirt python=3.11
conda activate reddirt
pip install torch transformers datasets peft trl accelerate bitsandbytes

# Step 1: Generate teacher trajectories (simulated if no 600B model)
python training/teacher_run.py --num-sessions 10000

# Step 2: Build distillation dataset
python training/distill_music.py --teacher-dir .reddirt/training/trajectories

# Step 3: Train 5B student
python training/train_music.py --config training/config_5b.json

# Step 4: Export GGUF (using llama.cpp convert script)
python convert-lora-to-gguf.py --model .reddirt/models/RedDirt-5B --out .reddirt/models/RedDirt-5B.Q4_K_M.gguf

# Step 5: Run with RedDirt-Tunes!
# Place .gguf in .reddirt/models/ and run:
cargo run --release
```

### Expected Timeline

| Stage | Time on RTX 4090 (24GB) | Time on CPU (cloud) |
|-------|---------------------------|---------------------|
| Teacher Runs (10K sessions, simulated) | Minutes | Minutes |
| Dataset Building | Minutes | Minutes |
| 5B Training (3 epochs, 100K steps) | 8–12 hours | 3–5 days |
| Export to GGUF | 30 minutes | 2–3 hours |
| Evaluation (gap-filling loop) | 2 hours | 1 day |
| **Total (single pass)** | **~12–16 hours** | **~4–6 days** |
| Multiple distill passes (recommended) | 2–3 days | 1–2 weeks |
