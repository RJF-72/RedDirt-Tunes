"""
RedDirt-Tunes Music Distillation Pipeline
600B Teacher → 5B Student for symbolic music generation.

Usage:
    python training/distill_music.py \
        --teacher-dir .reddirt/training/trajectories \
        --output-dir .reddirt/models/student_data \
        --mix-ratio 35,25,15,15,10 \
        --target-total 100000
"""
import json
import os
import random
import argparse
from pathlib import Path
from typing import List, Dict, Any


DATA_MIX = {
    "arrangement": 0.35,
    "stem_edit": 0.25,
    "nlu": 0.15,
    "nlp": 0.15,
    "remaster_mix": 0.10,
}

LOSS_WEIGHTS = {
    "chord_json": 2.0,
    "melody_tokens": 2.5,
    "arrangement_plan": 1.5,
    "stem_json": 1.2,
    "nlu": 1.0,
    "nlp": 0.8,
    "mix_params": 0.5,
    "lyric": 1.0,
}


def load_sessions(teacher_dir: Path) -> List[Dict[str, Any]]:
    sessions = []
    for traj_dir in teacher_dir.iterdir():
        if not traj_dir.is_dir():
            continue
        summary_path = traj_dir / "summary.json"
        if not summary_path.exists():
            continue
        with open(summary_path) as f:
            summary = json.load(f)
        steps = []
        for step_file in sorted(traj_dir.glob("step_*.json")):
            with open(step_file) as f:
                steps.append(json.load(f))
        sessions.append({"summary": summary, "steps": steps})
    return sessions


def bucket_steps(sessions: List[Dict]) -> Dict[str, List[Dict]]:
    buckets = {k: [] for k in DATA_MIX}
    for session in sessions:
        for step in session["steps"]:
            mode = step.get("mode", "").upper()
            if mode == "ARRANGEMENT":
                buckets["arrangement"].append(step)
            elif mode == "STEM_EDIT":
                buckets["stem_edit"].append(step)
            elif mode == "LYRIC":
                buckets["nlp"].append(step)
            elif mode == "MASTER":
                buckets["remaster_mix"].append(step)
            else:
                buckets["nlu"].append(step)
    return buckets


def build_sft_pairs(buckets: Dict[str, List[Dict]], target_total: int = 100_000) -> List[Dict]:
    pairs = []
    for bucket_name, ratio in DATA_MIX.items():
        pool = buckets.get(bucket_name, [])
        if not pool:
            continue
        needed = int(target_total * ratio)
        chosen = random.choices(pool, k=min(needed, len(pool)))
        for step in chosen:
            pair = {
                "system": "You are RedDirt-Tunes, a musical intelligence composing songs.",
                "instruction": step.get("input", ""),
                "output": json.dumps(step.get("output", {})),
                "meta": {
                    "mode": step.get("mode", "GENERATION"),
                    "weight": LOSS_WEIGHTS.get(bucket_name, 1.0),
                }
            }
            pairs.append(pair)
    random.shuffle(pairs)
    return pairs


def save_dataset(pairs: List[Dict], output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "distill_train.jsonl", "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    val_size = max(1, len(pairs) // 20)
    with open(output_dir / "distill_val.jsonl", "w", encoding="utf-8") as f:
        for p in pairs[:val_size]:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"[distill] Saved {len(pairs)} train, {val_size} val to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="RedDirt-Tunes Music Distillation")
    parser.add_argument("--teacher-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path(".reddirt/models/student_data"))
    parser.add_argument("--target-total", type=int, default=50_000)
    args = parser.parse_args()

    sessions = load_sessions(args.teacher_dir)
    print(f"[distill] Loaded {len(sessions)} teacher sessions")

    buckets = bucket_steps(sessions)
    for k, v in buckets.items():
        print(f"  {k}: {len(v)} steps")

    pairs = build_sft_pairs(buckets, target_total=args.target_total)
    save_dataset(pairs, args.output_dir)
    print("[distill] Done.")


if __name__ == "__main__":
    main()
