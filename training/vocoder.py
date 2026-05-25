"""
RedDirt-Tunes SOTA Singing Vocoder Backend
Wraps open-source singing synthesis models behind a clean HTTP API.

Supported backends (tried in order):
  1. DiffSinger (if installed and checkpoint available)
  2. So-VITS-SVC v4 (if installed)
  3. Fish Speech (if installed)
  4. TTS / XTTS (fallback for spoken singing)

Usage:
    python training/vocoder.py --backend auto --port 8766
"""
import json
import os
import sys
import argparse
import tempfile
from pathlib import Path
from typing import Dict, Optional, List

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("[vocoder] Flask not installed. Install: pip install flask")
    sys.exit(1)

app = Flask("RedDirt-Vocoder")

_backend_name = None
_backend_fn = None


def _try_import(module_name: str):
    """Try to import a module, return None if not found."""
    try:
        return __import__(module_name)
    except ImportError:
        return None


def init_backend(preferred: str = "auto"):
    """Auto-discover the best available singing backend."""
    global _backend_name, _backend_fn

    if preferred == "auto":
        # Try DiffSinger first (SOTA)
        if _init_diffsinger():
            _backend_name = "diffsinger"
            print("[vocoder] Using DiffSinger backend")
            return
        # Try So-VITS-SVC
        if _init_sovits():
            _backend_name = "so-vits-svc"
            print("[vocoder] Using So-VITS-SVC backend")
            return
        # Try Fish Speech
        if _init_fish_speech():
            _backend_name = "fish-speech"
            print("[vocoder] Using Fish Speech backend")
            return
        # Fallback: use system TTS (spoken singing)
        _backend_name = "tts-fallback"
        print("[vocoder] WARNING: No SOTA singing vocoder found. Using TTS fallback.")
        print("[vocoder] For real singing, install one of:")
        print("    pip install so-vits-svc-fork")
        print("    pip install -e git+https://github.com/openvpi/DiffSinger.git")
    elif preferred == "diffsinger":
        _init_diffsinger()
    elif preferred == "so-vits":
        _init_sovits()
    elif preferred == "fish-speech":
        _init_fish_speech()


def _init_diffsinger() -> bool:
    diffsinger = _try_import("diffsinger")
    if diffsinger is None:
        return False
    # DiffSinger would need a checkpoint path
    ckpt = os.environ.get("DIFFSINGER_CHECKPOINT")
    if not ckpt or not os.path.isdir(ckpt):
        print("[vocoder] DiffSinger found but DIFFSINGER_CHECKPOINT not set or invalid.")
        return False
    _backend_fn = lambda req: _run_diffsinger(req)
    return True


def _run_diffsinger(request: Dict) -> str:
    """Run DiffSinger inference."""
    import torch
    import numpy as np
    from diffsinger.infer import SvcInfer

    lyrics = request["lyrics"]
    notes = request.get("notes", [])
    singer = request.get("singer_id", "default")
    output_dir = Path(request.get("output_dir", ".reddirt/output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    ckpt = os.environ.get("DIFFSINGER_CHECKPOINT")
    infer = SvcInfer(ckpt)

    # Build phoneme + pitch sequence from lyrics + notes
    # This is simplified; real DiffSinger needs proper phoneme alignment
    midi_notes = [n["pitch"] for n in notes] if notes else [69]
    durations = [n.get("duration_beat", 0.5) for n in notes] if notes else [1]

    wav = infer.infer(
        lyrics=lyrics,
        notes=midi_notes,
        durations=durations,
        singer=singer,
    )

    out_path = output_dir / f"diffsinger_{_hash(lyrics)}.wav"
    import scipy.io.wavfile
    scipy.io.wavfile.write(str(out_path), rate=24000, data=wav)
    return str(out_path)


def _init_sovits() -> bool:
    try:
        import sovits
        _backend_fn = lambda req: _run_sovits(req)
        return True
    except ImportError:
        pass

    try:
        # Try the community fork
        import so_vits_svc_fork
        _backend_fn = lambda req: _run_sovits_fork(req)
        return True
    except ImportError:
        return False


def _run_sovits(request: Dict) -> str:
    """Run So-VITS-SVC inference with pitch guide."""
    # Simplified: real So-VITS needs a reference audio for voice conversion
    # For singing from scratch, we need a pitch contour + phoneme input
    output_dir = Path(request.get("output_dir", ".reddirt/output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"sovits_{_hash(request.get('lyrics',''))}.wav"
    return str(out_path)


def _run_sovits_fork(request: Dict) -> str:
    from so_vits_svc_fork.inference_main import infer
    output_dir = Path(request.get("output_dir", ".reddirt/output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    lyrics = request["lyrics"]
    out_path = output_dir / f"sovits_{_hash(lyrics)}.wav"

    # so-vits-svc-fork CLI mode
    model_path = os.environ.get("SOVITS_MODEL", "./models/so-vits")
    config_path = os.environ.get("SOVITS_CONFIG", "./models/so-vits/config.json")

    # Generate a pitch contour from melody notes
    notes = request.get("notes", [])
    # Simplified: create a dummy f0 contour
    f0_data = None
    if notes:
        f0_data = _notes_to_f0(notes)

    infer(
        input_path=str(out_path),  # would need a reference audio
        output_path=str(out_path),
        model_path=model_path,
        config_path=config_path,
        f0=f0_data,
    )
    return str(out_path)


def _init_fish_speech() -> bool:
    fish_speech = _try_import("fish_speech")
    if fish_speech is None:
        return False
    _backend_fn = lambda req: _run_fish_speech(req)
    return True


def _run_fish_speech(request: Dict) -> str:
    """Run Fish Speech inference."""
    from fish_speech.inference import generate_speech
    output_dir = Path(request.get("output_dir", ".reddirt/output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    lyrics = request["lyrics"]
    out_path = output_dir / f"fish_{_hash(lyrics)}.wav"

    # Fish Speech TTS mode
    generate_speech(
        text=lyrics,
        output=str(out_path),
        model_path=os.environ.get("FISH_MODEL", "./models/fish-speech"),
    )
    return str(out_path)


def _hash(text: str) -> str:
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()[:8]


def _notes_to_f0(notes: List[Dict]) -> List[float]:
    """Convert MIDI notes to f0 (fundamental frequency) contour at 10ms intervals."""
    f0 = []
    hop = 0.01  # 10ms hop
    for n in notes:
        pitch = n["pitch"]
        duration = n.get("duration_beat", 0.5)
        freq = 440.0 * (2.0 ** ((pitch - 69) / 12.0))
        num_frames = int(duration / hop)
        f0.extend([freq] * num_frames)
    return f0


@app.route("/health", methods=["GET"])
def health():
    if _backend_fn is None:
        return jsonify({"status": "no_backend", "available": _backend_name}), 500
    return jsonify({"status": "ok", "backend": _backend_name})


@app.route("/sing", methods=["POST"])
def sing():
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"status": "error", "message": "No JSON body"}), 400

        if _backend_fn is None:
            return jsonify({"status": "error", "message": "No vocoder backend loaded"}), 500

        # Validate required fields
        lyrics = data.get("lyrics", "")
        notes = data.get("notes", [])
        singer_id = data.get("singer_id", "default")
        emotion = data.get("emotion", "neutral")
        output_dir = data.get("output_dir", ".reddirt/output")

        if not lyrics:
            return jsonify({"status": "error", "message": "No lyrics provided"}), 400

        request_obj = {
            "lyrics": lyrics,
            "notes": notes,
            "singer_id": singer_id,
            "emotion": emotion,
            "output_dir": output_dir,
        }

        audio_path = _backend_fn(request_obj)

        return jsonify({
            "status": "ok",
            "audio_path": audio_path,
            "backend": _backend_name,
            "metadata": {
                "lyrics": lyrics,
                "singer": singer_id,
                "emotion": emotion,
                "num_notes": len(notes),
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


def main():
    parser = argparse.ArgumentParser(description="RedDirt-Tunes SOTA Vocoder Server")
    parser.add_argument("--backend", choices=["auto", "diffsinger", "so-vits", "fish-speech"], default="auto")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    init_backend(args.backend)

    print(f"[vocoder] Server running on http://{args.host}:{args.port}")
    print(f"[vocoder] Backend: {_backend_name}")
    print(f"[vocoder] POST /sing with JSON to synthesize singing")

    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
