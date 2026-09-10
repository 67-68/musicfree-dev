"""Feature extraction: beats CSV (from structure JSON), Chordino chords (Vamp),
and basic-pitch melody MIDI (best-effort).
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _which(*names: str) -> Optional[str]:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    # Fall back to the bundled copy under analysis/bin.
    local_bin = Path(__file__).resolve().parents[1] / "bin"
    for name in names:
        candidate = local_bin / name
        if candidate.exists():
            return str(candidate)
    return None


def write_beats_csv(beats: List[float], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["time"])
        for beat in beats:
            writer.writerow([f"{beat:.6f}"])
    return out_path


def run_chordino(audio_path: Path, out_dir: Path) -> Optional[Path]:
    """Run Sonic Annotator + Chordino. Returns chords.csv or None.

    Expected Vamp transform id for Chordino simple chord output:
    vamp:nnls-chroma:chordino:simplechord
    """
    annotator = _which("sonic-annotator")
    if not annotator:
        print("  [features] sonic-annotator not found; skipping Chordino chords", file=sys.stderr)
        return None

    csv_basedir = out_dir / "sonic-annotator"
    csv_basedir.mkdir(parents=True, exist_ok=True)
    transform = "vamp:nnls-chroma:chordino:simplechord"
    cmd = [
        annotator,
        "-q",
        "-d", transform,
        str(audio_path),
        "-w", "csv",
        "--csv-basedir", str(csv_basedir),
        "--csv-force",
    ]
    print(f"  [features] running: {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        print("  [features] sonic-annotator timed out; skipping Chordino", file=sys.stderr)
        return None
    if proc.returncode != 0:
        print(f"  [features] sonic-annotator failed: {proc.stderr[:300]}", file=sys.stderr)
        return None

    # Sonic Annotator writes CSV files named after the transform and audio file.
    candidates = list(csv_basedir.rglob("*.csv"))
    if not candidates:
        print("  [features] sonic-annotator produced no CSV", file=sys.stderr)
        return None

    source = candidates[0]
    dest = out_dir / "chords.csv"
    _normalize_chord_csv(source, dest)
    return dest


def _normalize_chord_csv(source: Path, dest: Path) -> None:
    """Convert a Sonic Annotator CSV into start,end,label rows.

    Chordino's ``simplechord`` output is a two-column CSV (time,label) with
    no duration.  Other Vamp outputs may be three-column (time,duration,value).
    Both are handled here; missing durations are filled from the next
    segment's start time.
    """
    rows: List[Dict[str, Any]] = []
    try:
        with open(source, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for parts in reader:
                parts = [p.strip() for p in parts]
                if not parts or not parts[0]:
                    continue
                if parts[0].startswith("#"):
                    continue
                if parts[0].lower() in ("time", "start"):
                    continue
                try:
                    start = float(parts[0])
                except ValueError:
                    continue

                end: Optional[float] = None
                if len(parts) >= 3:
                    try:
                        end = start + float(parts[1])
                        label = parts[2]
                    except ValueError:
                        label = parts[-1]
                else:
                    label = parts[-1]
                rows.append({"start": start, "end": end, "label": label.strip('"')})
    except Exception:
        shutil.copyfile(source, dest)
        return

    rows.sort(key=lambda r: r["start"])
    for idx, row in enumerate(rows):
        if row["end"] is None:
            if idx + 1 < len(rows):
                row["end"] = rows[idx + 1]["start"]
            else:
                row["end"] = row["start"] + 0.5

    with open(dest, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["start", "end", "label"])
        for row in rows:
            writer.writerow([f"{row['start']:.6f}", f"{row['end']:.6f}", row["label"]])
    print(f"  [features] wrote {dest} ({len(rows)} rows)")


def run_basic_pitch(audio_path: Path, out_dir: Path) -> Optional[Path]:
    """Run Spotify basic-pitch to transcribe melody. Returns melody.mid or None."""
    try:
        from basic_pitch.inference import predict_and_save
    except Exception:
        print("  [features] basic-pitch not installed; skipping melody MIDI", file=sys.stderr)
        return None

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    midi_path = out_dir / "melody.mid"

    try:
        import basic_pitch

        package_dir = Path(basic_pitch.__file__).resolve().parent
        model_path = package_dir / "saved_models" / "icassp_2022" / "nmp.onnx"
        if not model_path.exists():
            raise FileNotFoundError(f"basic-pitch model not found: {model_path}")
        predict_and_save(
            [str(audio_path)],
            str(out_dir),
            save_midi=True,
            sonify_midi=False,
            save_model_outputs=False,
            save_notes=False,
            model_or_model_path=str(model_path),
        )
    except Exception as exc:
        print(f"  [features] basic-pitch failed: {exc}", file=sys.stderr)
        return None

    # basic-pitch may write a differently-named MIDI; look for the newest .mid
    candidates = sorted(out_dir.glob("*.mid"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        print("  [features] basic-pitch produced no MIDI", file=sys.stderr)
        return None
    if candidates[0] != midi_path:
        candidates[0].rename(midi_path)
    print(f"  [features] wrote {midi_path}")
    return midi_path


def run_chords_librosa(audio_path: Path, out_dir: Path) -> Optional[Path]:
    """Fallback chord estimate from chroma + major/minor triad templates.

    Much rougher than Chordino, but useful when Vamp plugins are not installed.
    """
    try:
        import numpy as np
        import librosa
    except Exception:
        print("  [features] librosa not available; skipping chord fallback", file=sys.stderr)
        return None

    out_path = out_dir / "chords.csv"
    try:
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512)
        chroma = np.nan_to_num(chroma, nan=0.0, posinf=0.0, neginf=0.0)
        norm = np.linalg.norm(chroma, axis=0, keepdims=True)
        chroma = chroma / np.where(norm > 0, norm, 1.0)
        times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=512)

        major = np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0], dtype=float)
        minor = np.array([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0], dtype=float)
        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        templates = []
        labels = []
        for i, root in enumerate(notes):
            templates.append(np.roll(major, i))
            labels.append(root)
            templates.append(np.roll(minor, i))
            labels.append(root + "m")
        templates = np.array(templates)  # 24 x 12

        scores = np.einsum("ij,jk->ik", templates, chroma)  # 24 x frames
        best = np.argmax(scores, axis=0)
        # median-filter to suppress spurious frame-level flips
        best = np.pad(best, (4, 4), mode="edge")
        best = np.array([np.median(best[i:i + 9]) for i in range(len(best) - 8)]).astype(int)

        rows = []
        i = 0
        while i < len(best):
            j = i + 1
            while j < len(best) and best[j] == best[i]:
                j += 1
            start = float(times[i])
            end = float(min(times[-1] + (times[1] - times[0]), times[j - 1] + (times[1] - times[0])))
            rows.append((start, end, labels[best[i]]))
            i = j

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(["start", "end", "label"])
            for start, end, label in rows:
                writer.writerow([f"{start:.6f}", f"{end:.6f}", label])
        print(f"  [features] wrote {out_path} ({len(rows)} chord segments, librosa fallback)")
        return out_path
    except Exception as exc:
        print(f"  [features] librosa chord fallback failed: {exc}", file=sys.stderr)
        return None


def run_features(audio_path: Path, out_dir: Path, structure: Dict[str, Any]) -> Dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    beats = [float(b) for b in structure.get("beats", [])]
    beats_csv = write_beats_csv(beats, out_dir / "beats.csv")

    chords_csv = run_chordino(audio_path, out_dir)
    if chords_csv is None:
        chords_csv = run_chords_librosa(audio_path, out_dir)

    melody_mid = run_basic_pitch(audio_path, out_dir)

    return {
        "beats_csv": str(beats_csv),
        "chords_csv": str(chords_csv) if chords_csv else None,
        "melody_mid": str(melody_mid) if melody_mid else None,
    }


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Run feature extraction")
    parser.add_argument("audio")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--structure-json", required=True)
    args = parser.parse_args()
    structure = json.loads(Path(args.structure_json).read_text(encoding="utf-8"))
    features = run_features(Path(args.audio), Path(args.out_dir), structure)
    print(json.dumps(features, ensure_ascii=False, indent=2))
