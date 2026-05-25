"""
RedDirt-Tunes Model Server (Multi-Backend)
Supports: ACE-Step 1.5B (default), MusicGen (optional)

Setup for ACE-Step:
    conda create -n reddirt-musicenv python=3.11
    conda activate reddirt-musicenv
    pip install torch transformers accelerate soundfile
    pip install flask
    pip install flash-attn --no-build-isolation  # optional, speeds up inference
    python training/model_server.py --backend ace-step --port 8765

Usage from Rust:
    POST /generate
    {"prompt": "sad acoustic ballad in A minor", "duration": 10, "key": "Am", "tempo": 65}
"""
import json
import os
import argparse
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from flask import Flask, request, jsonify

app = Flask("RedDirt-ModelServer")

# Global handles
_model = None
_processor = None
_backend = None


def load_ace_step(model_id: str = "Amphion/ACE-Step-1.5B"):
    """Load ACE-Step 1.5B text-to-music model."""
    global _model, _processor, _backend
    try:
        from transformers import AutoModel, AutoTokenizer
        import torch
        print(f"[ace-step] Loading {model_id}...")
        _model = AutoModel.from_pretrained(model_id, trust_remote_code=True)
        _processor = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        _model.eval()
        _backend = "ace-step"
        print("[ace-step] Model loaded successfully. VRAM usage: ~3-4GB")
        return True
    except Exception as e:
        print(f"[ace-step] Failed to load: {e}")
        return False


def load_musicgen(model_id: str = "facebook/musicgen-small"):
    """Load MusicGen model (fallback)."""
    global _model, _processor, _backend
    try:
        from transformers import MusicgenForConditionalGeneration, AutoProcessor
        print(f"[musicgen] Loading {model_id}...")
        _model = MusicgenForConditionalGeneration.from_pretrained(model_id)
        _processor = AutoProcessor.from_pretrained(model_id)
        _backend = "musicgen"
        print("[musicgen] Model loaded. VRAM usage: ~5-6GB")
        return True
    except Exception as e:
        print(f"[musicgen] Failed to load: {e}")
        return False


def generate_ace_step(prompt: str, duration: int = 10, output_dir: Path = Path(".reddirt/output")) -> str:
    """Generate audio with ACE-Step."""
    global _model, _processor
    import torch
    
    output_dir.mkdir(parents=True, exist_ok=True)
    hash_id = hashlib.md5(prompt.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reddirt_ace_{timestamp}_{hash_id}.wav"
    path = output_dir / filename
    
    # ACE-Step specific inference
    text_input = f"Generate music: {prompt}. Length: {duration}s."
    inputs = _processor(text_input, return_tensors="pt")
    
    with torch.no_grad():
        audio_values = _model.generate(**inputs, max_new_tokens=duration * 50)
    
    import scipy
    # ACE-Step uses 24kHz
    scipy.io.wavfile.write(str(path), rate=24000, data=audio_values[0, 0].cpu().numpy())
    
    print(f"[ace-step] Generated: {path}")
    return str(path)


def generate_musicgen(prompt: str, duration: int = 10, output_dir: Path = Path(".reddirt/output")) -> str:
    """Generate audio with MusicGen (fallback)."""
    global _model, _processor
    
    output_dir.mkdir(parents=True, exist_ok=True)
    hash_id = hashlib.md5(prompt.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reddirt_gen_{timestamp}_{hash_id}.wav"
    path = output_dir / filename
    
    inputs = _processor(text=[prompt], padding=True, return_tensors="pt")
    audio_values = _model.generate(**inputs, max_new_tokens=duration * 50)
    
    import scipy
    rate = _model.config.audio_encoder.sampling_rate
    scipy.io.wavfile.write(str(path), rate=rate, data=audio_values[0, 0].cpu().numpy())
    
    print(f"[musicgen] Generated: {path}")
    return str(path)


@app.route("/health", methods=["GET"])
def health():
    if _model is None:
        return jsonify({"status": "model_not_loaded"}), 500
    return jsonify({"status": "ok", "backend": _backend, "model": app.config.get("MODEL_ID", "unknown")})


@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"status": "error", "message": "No JSON body"}), 400
        
        prompt = data.get("prompt", "")
        duration = data.get("duration", 10)
        key = data.get("key", "C")
        tempo = data.get("tempo", 120)
        mode = data.get("mode", "GENERATION")
        
        output_dir = app.config.get("OUTPUT_DIR", Path(".reddirt/output"))
        
        if _backend == "ace-step":
            audio_path = generate_ace_step(prompt, duration, output_dir)
        elif _backend == "musicgen":
            audio_path = generate_musicgen(prompt, duration, output_dir)
        else:
            return jsonify({"status": "error", "message": "No backend loaded"}), 500
        
        return jsonify({
            "status": "ok",
            "audio_path": audio_path,
            "backend": _backend,
            "metadata": {
                "prompt": prompt,
                "duration": duration,
                "key": key,
                "tempo": tempo,
                "mode": mode,
            }
        })
    except Exception as e:
        print(f"[server] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/generate_stems", methods=["POST"])
def generate_stems():
    """Placeholder: stem separation via Demucs/Spleeter."""
    try:
        data = request.get_json()
        audio_path = data.get("audio_path", "")
        if not os.path.exists(audio_path):
            return jsonify({"status": "error", "message": "Audio not found"}), 404
        
        # Placeholder: real stem separation would call Demucs here
        stems = {
            "vocals": audio_path.replace(".wav", "_vocals.wav"),
            "drums": audio_path.replace(".wav", "_drums.wav"),
            "bass": audio_path.replace(".wav", "_bass.wav"),
            "other": audio_path.replace(".wav", "_other.wav"),
        }
        return jsonify({"status": "ok", "stems": stems})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["ace-step", "musicgen"], default="ace-step")
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output-dir", type=Path, default=Path(".reddirt/output"))
    args = parser.parse_args()
    
    if args.backend == "ace-step":
        model_id = args.model_id or "Amphion/ACE-Step-1.5B"
        if not load_ace_step(model_id):
            print("[server] ACE-Step failed to load. Trying MusicGen fallback...")
            load_musicgen("facebook/musicgen-small")
    else:
        model_id = args.model_id or "facebook/musicgen-small"
        load_musicgen(model_id)
    
    if _model is None:
        print("[server] No model loaded. Exiting.")
        return
    
    app.config["MODEL"] = _model
    app.config["PROCESSOR"] = _processor
    app.config["MODEL_ID"] = model_id
    app.config["OUTPUT_DIR"] = args.output_dir
    
    print(f"[server] RedDirt Model Server running on http://{args.host}:{args.port}")
    print(f"[server] Backend: {_backend} | Model: {model_id}")
    print(f"[server] Send POST /generate with JSON to generate music.")
    
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
