# RedDirt-Tunes Complete Memory Footprint
## What Actually Hits Your RAM and VRAM

> **Bottom line:** The RedDirt-Tunes **Rust framework** (drivers, inference facade, MMIE, stem API, NLP/NLU, vocal synthesis controller, mastering controller) is < **75 MB**.
> The **model weights, KV cache, stem DSP backend, and vocal synthesis model** are external and loaded at runtime. They are the big memory hit.

---

## 1. RedDirt-Tunes Framework (< 75 MB, guaranteed)

| Component | Binary Size | Runtime RAM |
|-----------|-------------|-------------|
| `reddirt_driver` (modes, tools) | ~0.5 MB | ~2 MB |
| `reddirt_inference` (facade) | ~0.3 MB | ~1 MB |
| `reddirt_mmie` (scoring) | ~0.2 MB | ~1 MB |
| `reddirt_physical_model` (I/O) | ~0.2 MB | ~1 MB |
| `reddirt_stem` (stem API) | ~3.0 MB | ~5 MB |
| `reddirt_nlp` (intent/lyrics) | ~0.3 MB | ~1 MB |
| `reddirt_vocals` (sing API) | ~0.2 MB | ~1 MB |
| `reddirt_master` (master API) | ~0.3 MB | ~1 MB |
| `reddirt_capability` (profiler) | ~0.2 MB | ~1 MB |
| **Total Framework Binary** | **~5 MB** | — |
| **Runtime Framework** | — | **< 15 MB** |
| **Audio Buffers** | — | **20–50 MB** |
| **Disk Cache / Temp** | — | **10–20 MB** |
| **Framework + Buffers** | — | **< 75 MB** |

---

## 2. What Actually Hits Your RAM/VRAM (The Big Numbers)

When you run `cargo run --release`, these are the chunks that appear in your system memory:

### 2.1. 5B Model Weights (the largest hit)

| Quantization | File Size On Disk | Loaded into VRAM (GPU) | Loaded into RAM (CPU mmap) |
|--------------|-------------------|------------------------|----------------------------|
| FP16 (no quantization) | ~10 GB | ~10.5 GB | ~10 GB (slow) |
| Q5_K_M | ~3.5 GB | ~3.8 GB | ~3.5 GB |
| **Q4_K_M** | **~2.9 GB** | **~3.2 GB** | **~2.9 GB** |
| Q3_K_M | ~2.2 GB | ~2.5 GB | ~2.2 GB |
| **Q2_K** | **~1.7 GB** | **~2.0 GB** | **~1.7 GB** |

**How to control this:**
- Put a smaller `.gguf` in `.reddirt/models/`
- Mobile tier auto-selects the smallest file
- You can also set `export REDDIRT_MODEL_MAX_MB=2000` to enforce a hard cap

---

### 2.2. KV Cache (scales with context length)

The KV cache is **NOT the model weights** — it's temporary memory used during token generation. It grows with every token you generate.

| Context Length | Q2 Cache | Q4 Cache | Q8 Cache | FP16 Cache |
|----------------|----------|----------|----------|------------|
| 512 tokens (Mobile) | ~30 MB | ~60 MB | ~120 MB | ~240 MB |
| 1,024 tokens | ~60 MB | ~120 MB | ~240 MB | ~480 MB |
| 2,048 tokens (Live) | ~120 MB | ~240 MB | ~480 MB | ~960 MB |
| 4,096 tokens (Studio) | ~240 MB | ~480 MB | ~960 MB | ~1.9 GB |
| 8,192 tokens (Ultra) | ~480 MB | ~960 MB | ~1.9 GB | ~3.8 GB |

**How to control this:**
- The capability profile caps this per tier:
  - Mobile → 512 max context
  - Live → 2,048 max context
  - Studio → 8,192 max context
- You can tighten it with `export REDDIRT_KV_CACHE_MAX_MB=512`

---

### 2.3. Stem Separation Backend (external DSP)

When you trigger stem separation, `reddirt_stem` calls an external engine. This is **NOT** inside the 5B model.

| Backend | When it loads | RAM hit | Quality |
|---------|---------------|---------|---------|
| Demucs v4 (hybrid) | When "separate" is called | **+3.5 GB** | Best |
| Spleeter (5-stem) | When "separate" is called | **+2.0 GB** | Good |
| Onnxruntime (light) | When "separate" is called | **+1.0 GB** | Fair |
| STFT/RFFT (planned native) | When "separate" is called | **+256 MB** | Basic |
| **Placeholder (stub)** | Never | **0 MB** | None |

**How to control this:**
- Tier limits:
  - Studio → full Demucs
  - Live → Spleeter or Onnx
  - Mobile → Onnx light or stub
- You can override: `export REDDIRT_STEM_BACKEND=none` to skip stems entirely

---

### 2.4. Vocal Synthesis (sing the lyrics)

When you ask RedDirt to "sing," the vocal synthesis engine loads a vocoder model.

| Vocoder Model | When it loads | RAM hit | Quality |
|---------------|---------------|---------|---------|
| DiffSinger (full) | When "sing" mode triggered | **+2.5 GB** | Best |
| N-Singer (medium) | When "sing" mode triggered | **+1.2 GB** | Good |
| Onnx vocoder (light) | When "sing" mode triggered | **+500 MB** | Fair |
| **Silent placeholder** | On every "sing" → returns zeros | **0 MB** | No sound until external vocoder added |

**Current status:** Stub only (sine wave placeholder). When real vocoder is added:
- Mobile tier → 500 MB Onnx or skip
- Live tier → 1.2 GB N-Singer
- Studio tier → 2.5 GB DiffSinger

---

### 2.5. Mastering DSP (radio-ready)

Mastering runs **in-place** on existing buffers. It adds almost zero memory.

| Mode | Additional RAM | Notes |
|------|----------------|-------|
| EQ + Compression + Limiting | **< 5 MB** | Processes buffer in-place |
| Loudness normalization | **< 1 MB** | RMS scan + single scalar gain |
| **Total additional** | **~0 MB** | Negligible |

---

## 3. What Actually Hits RAM vs VRAM (GPU vs CPU)

### If you have a GPU (NVIDIA)

| Component | VRAM | RAM | Notes |
|-----------|------|-----|-------|
| 5B Model (Q4) | **3.2 GB** | 0 | Loaded into GPU memory |
| KV Cache (2K) | **240 MB** | 0 | Lives on GPU during generation |
| Stem Backend | 0 | **+1–3.5 GB** | Usually CPU-based (PyTorch/Onnx) |
| Vocal Synthesis | 0 | **+500 MB–2.5 GB** | Usually CPU-based |
| Framework | 0 | **< 15 MB** | Rust runtime |
| Buffers | 0 | **20–50 MB** | Audio streams |
| **Total GPU** | **~3.5–6 GB** | — | Depends on model size + context |
| **Total RAM** | — | **~1.5–6 GB** | Stem/vocal backend dominates |
| **TOTAL MEMORY** | — | **~5.5–12 GB** | VRAM + RAM combined |

### If you have NO GPU (CPU only)

| Component | VRAM | RAM | Notes |
|-----------|------|-----|-------|
| 5B Model (Q4) | 0 | **2.9 GB** | mmap from disk |
| KV Cache (2K) | 0 | **240 MB** | Lives in RAM |
| Stem Backend | 0 | **+1–3.5 GB** | CPU-based |
| Vocal Synthesis | 0 | **+500 MB–2.5 GB** | CPU-based |
| Framework | 0 | **< 15 MB** | Rust runtime |
| Buffers | 0 | **20–50 MB** | Audio streams |
| **Total** | **0** | **~4.5–9 GB** | Everything in system RAM |

---

## 4. Real-World Scenarios (What You Will Actually See)

### Scenario A: Laptop, no GPU, 8GB RAM

| What you do | What loads | RAM used | Will it fit? |
|-------------|------------|----------|--------------|
| Boot framework | RedDirt binary + buffers | ~50 MB | ✅ Yes |
| Load Q2 model (Mobile) | 1.7 GB mmap | ~1.7 GB | ✅ Yes |
| Generate a song (1K context) | KV cache 60 MB + buffers | ~1.8 GB | ✅ Yes |
| Stem separation (Onnx light) | +1 GB backend | ~2.8 GB | ✅ Yes |
| Sing lyrics (Onnx vocoder) | +500 MB | ~3.3 GB | ✅ Yes |
| Master radio-ready | +0 MB | ~3.3 GB | ✅ Yes |
| **TOTAL** | — | **~3.3 GB** | **✅ Fits in 8GB** |

### Scenario B: Desktop, 6GB VRAM (GTX 1060), 16GB RAM

| What you do | VRAM | RAM | Notes |
|-------------|------|-----|-------|
| Boot framework | 0 | ~50 MB | — |
| Load Q4 model | **3.2 GB** | 0 | GPU loaded |
| Generate (2K context) | **+240 MB** | 0 | GPU loaded |
| Stem (Spleeter) | 0 | **+2 GB** | CPU backend |
| Sing (N-Singer) | 0 | **+1.2 GB** | CPU backend |
| Master | 0 | ~0 MB | In-place |
| **TOTAL** | **~3.5 GB VRAM** | **~3.3 GB RAM** | **✅ Fits** |

### Scenario C: Studio Rig, 12GB VRAM (RTX 3060), 32GB RAM

| What you do | VRAM | RAM | Notes |
|-------------|------|-----|-------|
| Boot framework | 0 | ~75 MB | — |
| Load Q5 model | **3.8 GB** | 0 | GPU loaded |
| Generate (8K context) | **+1 GB** | 0 | Long context |
| Stem (Demucs) | 0 | **+3.5 GB** | Best quality |
| Sing (DiffSinger) | 0 | **+2.5 GB** | Best quality |
| Master | 0 | ~0 MB | In-place |
| **TOTAL** | **~4.8 GB VRAM** | **~6.1 GB RAM** | **✅ Comfortable** |

---

## 5. How to Stay Under Your Budget

| Your Machine | Recommended Config | Expected Total |
|--------------|-------------------|----------------|
| 4GB RAM, no GPU | Q2, 512 context, no stems, no singing | **~1.8 GB** |
| 8GB RAM, no GPU | Q2, 1K context, Onnx stems, Onnx vocal | **~3.3 GB** |
| 16GB RAM, 4GB GPU | Q3, 2K context, CPU stems, Onnx vocal | **~3.5 GB VRAM + ~3 GB RAM** |
| 32GB RAM, 8GB GPU | Q4, 4K context, Spleeter, N-Singer | **~3.5 GB VRAM + ~5 GB RAM** |
| 64GB RAM, 12GB GPU | Q5, 8K context, Demucs, DiffSinger | **~5 GB VRAM + ~6 GB RAM** |

---

## 6. MMIE Memory Guard

The MMIE scoring engine penalizes memory overuse:

| Tier | RAM Target | Penalty if exceeded |
|------|------------|---------------------|
| Mobile | 1.5 GB | –1.0 reward |
| Live | 3.0 GB | –0.5 reward |
| Studio | 5.0 GB | –0.3 reward |

If a session exceeds target, the trajectory is **discarded** and never used for training. This keeps the system honest about memory.

---

## 7. TL;DR — What Hits Your Machine

| Item | Size | When it appears |
|------|------|-----------------|
| **RedDirt framework** | < 75 MB | Always |
| **5B model weights** | 1.7–10 GB | When model loads |
| **KV cache** | 30 MB–2 GB | During token generation |
| **Stem backend** | 256 MB–3.5 GB | When separating stems |
| **Vocal synthesis** | 0–2.5 GB | When singing |
| **Mastering** | ~0 MB | When mastering |
| **TOTAL minimum** | **~2 GB** | Q2 model, no GPU, stubs |
| **TOTAL recommended** | **~4–6 GB** | Q4 model, 6GB GPU, real backends |
| **TOTAL studio** | **~8–12 GB** | Q5 model, 12GB GPU, best backends |

---

## 8. How We Keep the Framework Under 75MB

1. **Zero model weights in binary.** Model is external `.gguf`.
2. **Zero DSP in binary.** Stem/vocal backends are external libraries.
3. **Streaming audio.** 1-second blocks, not full tracks.
4. **Aggressive cleanup.** Buffers dropped immediately after use.
5. **Tier enforcement.** Profile hard-caps everything at boot.

---

**Document:** `docs/MEMORY.md`
**Version:** 1.0
**Last updated:** With vocal synthesis + mastering
