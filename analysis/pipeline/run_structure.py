"""Run all-in-one-infer (structure + source separation)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

_ANALYSIS_DIR = Path(__file__).resolve().parents[1]
for _var, _sub in (("MPLCONFIGDIR", "mpl"), ("TORCH_HOME", "torch"), ("HF_HOME", "hf")):
    if not os.environ.get(_var):
        _target = _ANALYSIS_DIR / ".cache" / _sub
        _target.mkdir(parents=True, exist_ok=True)
        os.environ[_var] = str(_target)


def run_structure(
    audio_path: Path,
    out_dir: Path,
    *,
    device: str = "cpu",
    overwrite: bool = True,
) -> Dict[str, Any]:
    """Analyze one audio file and return the raw all-in-one-infer result dict."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from allin1_infer import analyze
    except Exception as exc:
        raise RuntimeError(
            "all-in-one-infer is not installed in the venv. "
            "Run: analysis/venv/bin/pip install all-in-one-infer"
        ) from exc

    result = analyze(
        str(audio_path),
        out_dir=str(out_dir / "struct"),
        demix_dir=str(out_dir / "demix"),
        spec_dir=str(out_dir / "spec"),
        keep_byproducts=True,
        device=device,
        overwrite=overwrite,
    )

    raw = asdict(result)
    # Path objects don't survive json.dump; normalize.
    raw["path"] = str(raw.get("path", audio_path))
    raw["segments"] = [
        {"start": float(s["start"]), "end": float(s["end"]), "label": s["label"]}
        for s in raw.get("segments", [])
    ]
    raw["beats"] = [float(b) for b in raw.get("beats", [])]
    raw["downbeats"] = [float(b) for b in raw.get("downbeats", [])]
    raw["beat_positions"] = [int(p) for p in raw.get("beat_positions", [])]
    raw.pop("activations", None)
    raw.pop("embeddings", None)

    raw_path = out_dir / "structure.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return raw


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Run all-in-one-infer structure analysis")
    parser.add_argument("audio")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    result = run_structure(Path(args.audio), Path(args.out_dir), device=args.device)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:1000])
