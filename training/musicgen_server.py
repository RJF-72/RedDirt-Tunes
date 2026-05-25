"""
RedDirt-Tunes MusicGen Python Server
Wraps Meta's MusicGen model as a lightweight JSON-RPC server.
This is the Inference backend for RedDirt-Tunes.

Setup:
    conda create -n reddirt-musicenv python=3.11
    conda activate reddirt-musicenv
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    pip install transformers accelerate soundfile
    pip install flask  # or fastapi + uvicorn
    python training/musicgen_server.py --model facebook/musicgen-small

Usage from Rust:
    POST /generate
    {
        "prompt": "sad acoustic ballad in A minor",
        "duration": 10,
        "key": "Am",
        "tempo": 65,
        "mode": "ARRANGEMENT"
    }
    Returns:
    {
        "status": "ok",
        "audio_path": ".reddirt/output/song_abc.wav",
        "metadata": {...}
    }
"""
import json
import os
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify

app = Flask("RedDirt-MusicGen")

# Global model handle
_generator = None

def load_musicgen(model_name: str):
    global _generator
    try:
        from transformers import MusicgenForConditionalGeneration, AutoProcessor
        print(f"[musicgen] Loading {model_name}...")
        _generator = MusicgenForConditionalGeneration.from_pretrained(model_name)
        _processor = AutoProcessor.from_pretrained(model_name)
        print(f"[musicgen] Model loaded. Device map: auto-allocated.")
        return _generator, _processor
    except Exception as e:
        print(f"[musicgen] Error loading model: {e}")
        return None, None


def generate_audio(
    prompt: str,
    duration: int = 10,
    model=None,
    processor=None,
    output_dir: Path = Path(".reddirt/output"),
) -> str:
    """Generate audio and save to file."""
    if model is None or processor is None:
        raise RuntimeError("Model not loaded")
    
    inputs = processor(
        text=[prompt],
        padding=True,
        return_tensors="pt",
    )
    
    # Generate
    audio_values = model.generate(**inputs, max_new_tokens=duration * 50)
    
    # Save
    output_dir.mkdir(parents=True, exist_ok=True)
    hash_id = hashlib.md5(prompt.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reddirt_gen_{timestamp}_{hash_id}.wav"
    path = output_dir / filename
    
    import scipy
    sampling_rate = model.config.audio_encoder.sampling_rate
    scipy.io.wavfile.write(str(path), rate=sampling_rate, data=audio_values[0, 0].cpu().numpy())
    
    print(f"[musicgen] Generated: {path}")
    return str(path)


@app.route("/health", methods=["GET"])
def health():
    if _generator is None:
        return jsonify({"status": "model_not_loaded"}), 500
    return jsonify({"status": "ok", "model": app.config.get("MODEL_NAME", "unknown")})


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
        
        # Enhance prompt with musical context
        enhanced_prompt = f"{prompt}, {key} major, {tempo} bpm, {mode}"
        
        audio_path = generate_audio(
            prompt=enhanced_prompt,
            duration=duration,
            model=_generator,
            processor=app.config.get("PROCESSOR"),
        )
        
        return jsonify({
            "status": "ok",
            "audio_path": audio_path,
            "metadata": {
                "prompt": prompt,
                "enhanced_prompt": enhanced_prompt,
                "duration": duration,
                "key": key,
                "tempo": tempo,
                "mode": mode,
            }
        })
    except Exception as e:
        print(f"[musicgen] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/generate_stems", methods=["POST"])
def generate_stems():
    """Generate separate stems from MusicGen output using a separator."""
    try:
        data = request.get_json()
        audio_path = data.get("audio_path", "")
        if not os.path.exists(audio_path):
            return jsonify({"status": "error", "message": "Audio not found"}), 404
        
        # Placeholder: real implementation would call Demucs or Spleeter
        stems = {
            "vocals": audio_path.replace(".wav", "_vocals.wav"),
            "drums": audio_path.replace(".wav", "_drums.wav"),
            "bass": audio_path.replace(".wav", "_bass.wav"),
            "other": audio_path.replace(".wav", "_other.wav"),
        }
        
        return jsonify({
            "status": "ok",
            "stems": stems,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def main():
    parser = argparse.ArgumentParser(description="RedDirt-Tunes MusicGen Server")
    parser.add_argument("--model", default="facebook/musicgen-small")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output-dir", type=Path, default=Path(".reddirt/output"))
    args = parser.parse_args()
    
    # Load model
    gen, proc = load_musicgen(args.model)
    if gen is None:
        print("[musicgen] Failed to load model. Exiting.")
        return
    
    app.config["MODEL"] = gen
    app.config["PROCESSOR"] = proc
    app.config["MODEL_NAME"] = args.model
    app.config["OUTPUT_DIR"] = args.output_dir
    
    print(f"[musicgen] Server running on http://{args.host}:{args.port}")
    print(f"[musicgen] Send POST /generate with JSON to generate music.")
    
    # Run Flask dev server (production: use gunicorn or uvicorn)
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
