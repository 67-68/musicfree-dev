"""Normalize raw analysis artifacts into analysis.json."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import librosa
except Exception:  # pragma: no cover
    librosa = None


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\-]+", "-", text.strip(), flags=re.UNICODE)
    text = re.sub(r"-+", "-", text)
    return text.strip("-") or "track"


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_stems(search_root: Path) -> Dict[str, str]:
    """Locate demucs stems recursively under search_root.

    Demucs writes files like <root>/htdemucs/<track>/vocals.wav.
    """
    wanted = {"vocals", "drums", "bass", "other"}
    found: Dict[str, str] = {}
    for path in search_root.rglob("*.wav"):
        stem = path.stem.lower()
        if stem in wanted and stem not in found:
            found[stem] = str(path)
        if len(found) == len(wanted):
            break
    return found


def load_structure_json(out_dir: Path) -> Optional[Dict[str, Any]]:
    """Find the all-in-one-infer result JSON under out_dir."""
    for pattern in ("struct/*.json", "*.json"):
        for path in sorted(out_dir.glob(pattern)):
            data = read_json(path)
            if isinstance(data, dict) and "segments" in data and "bpm" in data:
                return data
    return None


def duration_sec(audio_path: Path) -> float:
    if librosa is not None:
        try:
            return float(librosa.get_duration(path=str(audio_path)))
        except TypeError:
            return float(librosa.get_duration(filename=str(audio_path)))
        except Exception:
            pass
    return 0.0


def build_analysis(
    audio_path: Path,
    out_dir: Path,
    *,
    title: Optional[str] = None,
    artist: Optional[str] = None,
    structure_json: Optional[Path] = None,
    beats_csv: Optional[Path] = None,
    chords_csv: Optional[Path] = None,
    melody_mid: Optional[Path] = None,
    genius_json: Optional[Path] = None,
    report_md: Optional[Path] = None,
    duration_source: Optional[Path] = None,
) -> Dict[str, Any]:
    audio_path = Path(audio_path).resolve()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_structure: Optional[Dict[str, Any]]
    if structure_json is not None:
        raw_structure = read_json(Path(structure_json))
    else:
        raw_structure = load_structure_json(out_dir)

    if raw_structure is not None:
        structure = raw_structure
    else:
        structure = {"bpm": 0, "beats": [], "downbeats": [], "segments": []}

    track_title = title or Path(audio_path).stem
    track_artist = artist or ""

    stems = find_stems(out_dir)
    genius_data: Dict[str, Any] = {}
    if genius_json is not None and Path(genius_json).exists():
        genius_data = read_json(Path(genius_json))

    analysis = {
        "track": {
            "title": track_title,
            "artist": track_artist,
            "path": str(audio_path),
            "duration_sec": duration_sec(Path(duration_source) if duration_source else audio_path),
            "bpm": structure.get("bpm", 0),
        },
        "stems": stems,
        "structure": structure.get("segments", []),
        "beats": structure.get("beats", []),
        "downbeats": structure.get("downbeats", []),
        "chords_csv": str(chords_csv) if chords_csv else None,
        "chords": _read_csv(chords_csv) if chords_csv else [],
        "beats_csv": str(beats_csv) if beats_csv else None,
        "melody_midi": str(melody_mid) if melody_mid else None,
        "genius": genius_data,
        "report_md": str(report_md) if report_md else None,
    }
    target = out_dir / "analysis.json"
    write_json(target, analysis)
    return analysis


def _read_csv(path: Optional[Path]) -> List[Dict[str, Any]]:
    if not path or not Path(path).exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                try:
                    rows.append({"start": float(parts[0]), "end": float(parts[1]), "label": parts[2]})
                except ValueError:
                    continue
    return rows


if __name__ == "__main__":  # pragma: no cover
    print("normalize.py is a library; run song_analyze.py")
    sys.exit(1)
