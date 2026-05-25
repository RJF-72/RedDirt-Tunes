"""
RedDirt-Tunes Model Server (ACE-Step 1.5B)
Wraps the ACE-Step 1.5B text-to-music model as a JSON-RPC server.

Setup:
    conda create -n reddirt-musicenv python=3.11
    conda activate reddirt-musicenv
    pip install torch transformers accelerate soundfile flask scipy
    python training/model_server.py --model-id Amphion/ACE-Step-1.5B

Usage from Rust:
    POST /generate
    {
        "prompt": "sad acoustic ballad in A minor",
        "duration": 10,
        "key": "Am",
        "tempo": 65
    }
"""
import json
import os
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict
from flask import Flask, request, jsonify

app = Flask("RedDirt-ACEStep")

_model = None
_processor = None
_MODEL_ID = None

def load_ace_step(model_id: str):
    """Load ACE-Step 1.5B text-to-music model."""
    global _model, _processor
    try:
        from transformers import AutoModel, AutoTokenizer
        import torch
        print(f"[ace-step] Loading {model_id}...")
        _model = AutoModel.from_pretrained(model_id, trust_remote_code=True)
        _processor = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        _model.eval()
        if torch.cuda.is_available():
            _model = _model.cuda()
            print(f"[ace-step] Moved model to CUDA: {torch.cuda.get_device_name(0)}")
        else:
            print("[ace-step] Running on CPU (slower)")
        print(f"[ace-step] Model loaded successfully")
        return True
    except Exception as e:
        print(f"[ace-step] Failed to load: {e}")
        return False

def generate_audio(prompt: str, duration: int, output_dir: Path) -
        str:
    """Generate audio with ACE-Step and save to disk."""
    import torch
    import scipy
    global _model, _processor
    output_dir.mkdir(parents=True, exist_ok=True)
    hash_id = hashlib.md5(prompt.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reddirt_ace_{timestamp}_{hash_id}.wav"
    path = output_dir / filename
    text_input = f"Generate music: {prompt}. Length: {duration}s."
    inputs = _processor(text_input, return_tensors="pt").to(_model.device)
    with torch.no_grad():
        audio_values = _model.generate(**inputs, max_new_tokens=duration * 50)
    rate = 24000  # ACE-Step sample rate
    scipy.io.wavfile.write(str(path), rate=rate, data=audio_values[0, 0].cpu().numpy())
    print(f"[ace-step] Generated: {path} ({duration}s at {rate}Hz)")
    return str(path)

@app.route("/health", methods=["GET"])
def health():
    if _model is None:
        return jsonify({"status": "model_not_loaded"}), 500
    return jsonify({
        "status": "ok",
        "backend": "ace-step",
        "model": _MODEL_ID or "unknown",
        "device": str(next(_model.parameters()).device)
    })

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
        audio_path = generate_audio(prompt, duration, output_dir)
        return jsonify({
            "status": "ok",
            "audio_path": audio_path,
            "backend": "ace-step",
            "metadata": {
                "prompt": prompt,
                "duration": duration,
                "key": key,
                "tempo": tempo,
                "mode": mode,
            }
        })
    except Exception as e:
        print(f"[ace-step] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/generate_stems", methods=["POST"])
def generate_stems():
    try:
        data = request.get_json()
        audio_path = data.get("audio_path", "")
        if not os.path.exists(audio_path):
            return jsonify({"status": "error", "message": "Audio not found"}), 404
        # Placeholder: stem separation would call a separator here
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
    parser = argparse.ArgumentParser(description="RedDirt-Tunes ACE-Step Server")
    parser.add_argument("--model-id", default="Amphion/ACE-Step-1.5B")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output-dir", type=Path, default=Path(".reddirt/output"))
    args = parser.parse_args()
    model_id = args.model_id
    global _MODEL_ID
    _MODEL_ID = model_id
    if not load_ace_step(model_id):
        print("[ace-step] No model loaded. Exiting.")
        return
    app.config["OUTPUT_DIR"] = args.output_dir
    print(f"[ace-step] Server running on http://{args.host}:{args.port}")
    print(f"[ace-step] Model: {model_id}")
    print(f"[ace-step] POST /generate with JSON to generate music")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)

if __name__ == "__main__":
    main()
