#!/usr/bin/env python3
"""song-analyze — CLI orchestrator for song structure/features/Genius/SV.

Subcommands:
    run        <audio> [--artist A --title T] [--genius-token TOKEN] [--device D]
    structure  <audio> [--device D]
    features   <audio>
    genius     <artist> <title> [--out-dir DIR] [--token TOKEN]
    open       <audio>
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
ANALYSIS_DIR = HERE.parent
CACHE_DIR = ANALYSIS_DIR / ".cache"
OUTPUT_DIR = ANALYSIS_DIR / "output"

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))


def _setup_env() -> None:
    """Ensure matplotlib/torch/huggingface caches go to a writable local dir,
    and make the locally built Vamp plugins discoverable by sonic-annotator."""
    for var, sub in (
        ("MPLCONFIGDIR", "mpl"),
        ("TORCH_HOME", "torch"),
        ("HF_HOME", "hf"),
    ):
        if not os.environ.get(var):
            target = CACHE_DIR / sub
            target.mkdir(parents=True, exist_ok=True)
            os.environ[var] = str(target)

    vamp_dir = ANALYSIS_DIR / "vamp"
    if vamp_dir.is_dir():
        existing = os.environ.get("VAMP_PATH", "")
        parts = [p for p in existing.split(os.pathsep) if p]
        if str(vamp_dir) not in parts:
            parts.insert(0, str(vamp_dir))
            os.environ["VAMP_PATH"] = os.pathsep.join(parts)


_setup_env()

from pipeline.audio_prep import prepare_audio, prepared_audio_if_exists  # noqa: E402
from pipeline.normalize import build_analysis, slugify  # noqa: E402
from pipeline.run_features import run_features  # noqa: E402
from pipeline.run_genius import run_genius  # noqa: E402
from pipeline.run_structure import run_structure  # noqa: E402


def _out_dir_for(audio: Path, artist: Optional[str], title: Optional[str]) -> Path:
    audio = Path(audio)
    stem = audio.stem
    parts = []
    if artist:
        parts.append(slugify(artist))
    if title:
        parts.append(slugify(title))
    if not parts:
        parts.append(slugify(stem))
    return OUTPUT_DIR / "-".join(parts)


def _write_report_skeleton(out_dir: Path, analysis: dict) -> Path:
    report = out_dir / "report.md"
    track = analysis["track"]
    lines = [
        f"# {track.get('title') or Path(analysis['track']['path']).stem}",
        "",
        f"- 艺术家: {track.get('artist') or '未知'}",
        f"- BPM: {track.get('bpm', 0)}",
        f"- 时长: {track.get('duration_sec', 0):.1f}s",
        "",
        "## 结构时间轴",
        "",
        "| 开始 | 结束 | 段落 |",
        "| --- | --- | --- |",
    ]
    for seg in analysis.get("structure", []):
        lines.append(f"| {seg['start']:.1f} | {seg['end']:.1f} | {seg['label']} |")
    lines += [
        "",
        "## Agent 讲解",
        "",
        "（由 Agent 阅读 analysis.json 与 genius.json 后填写）",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def cmd_run(args) -> int:
    audio = Path(args.audio)
    if not audio.exists():
        print(f"audio not found: {audio}", file=sys.stderr)
        return 1
    out_dir = _out_dir_for(audio, args.artist, args.title)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"==> out_dir: {out_dir}")

    try:
        analysis_audio = prepare_audio(audio, out_dir)
    except RuntimeError as exc:
        print(f"audio prepare failed: {exc}", file=sys.stderr)
        return 1

    print("==> [1/4] structure (all-in-one-infer)")
    run_structure(analysis_audio, out_dir, device=args.device)

    structure = {}
    structure_path = out_dir / "structure.json"
    if structure_path.exists():
        import json

        structure = json.loads(structure_path.read_text(encoding="utf-8"))

    print("==> [2/4] features (beats/chords/melody)")
    run_features(analysis_audio, out_dir, structure)

    print("==> [3/4] genius (optional)")
    genius_path = None
    if args.artist and args.title:
        genius_path = run_genius(
            out_dir,
            artist=args.artist,
            title=args.title,
            token=args.genius_token,
        )

    print("==> [4/4] normalize + report")
    beats_path = out_dir / "beats.csv"
    chords_path = out_dir / "chords.csv"
    melody_path = out_dir / "melody.mid"
    analysis = build_analysis(
        audio,
        out_dir,
        title=args.title,
        artist=args.artist,
        structure_json=structure_path if structure_path.exists() else None,
        beats_csv=beats_path if beats_path.exists() else None,
        chords_csv=chords_path if chords_path.exists() else None,
        melody_mid=melody_path if melody_path.exists() else None,
        genius_json=genius_path,
        duration_source=analysis_audio,
    )
    report = _write_report_skeleton(out_dir, analysis)
    analysis["report_md"] = str(report)
    import json

    (out_dir / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    print("==> done")
    print(json.dumps(analysis, ensure_ascii=False, indent=2))
    print(f"report: {report}")
    print("下一步：song-analyze open <audio> 用 Sonic Visualiser 打开，或让 Agent 阅读 analysis.json 写讲解。")
    return 0


def cmd_structure(args) -> int:
    audio = Path(args.audio)
    if not audio.exists():
        print(f"audio not found: {audio}", file=sys.stderr)
        return 1
    out_dir = _out_dir_for(audio, None, None)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        analysis_audio = prepare_audio(audio, out_dir)
    except RuntimeError as exc:
        print(f"audio prepare failed: {exc}", file=sys.stderr)
        return 1
    run_structure(analysis_audio, out_dir, device=args.device)
    print(out_dir / "structure.json")
    return 0


def _find_out_dir_for_audio(audio: Path, explicit: Optional[str] = None) -> Path:
    if explicit:
        return Path(explicit)
    needle = str(audio.resolve())
    try:
        import json as _json
    except Exception:
        pass
    else:
        for analysis_file in OUTPUT_DIR.rglob("analysis.json"):
            try:
                data = _json.loads(analysis_file.read_text(encoding="utf-8"))
                if data.get("track", {}).get("path") == needle:
                    return analysis_file.parent
            except Exception:
                continue
    return _out_dir_for(audio, None, None)


def cmd_features(args) -> int:
    audio = Path(args.audio)
    if not audio.exists():
        print(f"audio not found: {audio}", file=sys.stderr)
        return 1
    out_dir = _find_out_dir_for_audio(audio, getattr(args, "out_dir", None))
    structure = {}
    structure_path = out_dir / "structure.json"
    if structure_path.exists():
        import json

        structure = json.loads(structure_path.read_text(encoding="utf-8"))
    else:
        print("structure.json not found; run `structure` first", file=sys.stderr)
        return 1
    try:
        analysis_audio = prepare_audio(audio, out_dir)
    except RuntimeError as exc:
        print(f"audio prepare failed: {exc}", file=sys.stderr)
        return 1
    features = run_features(analysis_audio, out_dir, structure)
    print(features)
    return 0


def cmd_genius(args) -> int:
    out_dir = Path(args.out_dir) if args.out_dir else Path.cwd()
    path = run_genius(out_dir, artist=args.artist, title=args.title, token=args.token)
    if path is None:
        return 1
    print(path)
    return 0


def _find_sv_command() -> Optional[list]:
    found = shutil.which("sonic-visualiser")
    if found:
        return [found]
    # macOS app bundle: prefer the local copy in analysis/apps, then /Applications.
    for app_path in (
        ANALYSIS_DIR / "apps" / "Sonic Visualiser.app",
        Path("/Applications/Sonic Visualiser.app"),
    ):
        binary = Path(app_path) / "Contents" / "MacOS" / "Sonic Visualiser"
        if binary.exists():
            return [str(binary)]
        if Path(app_path).exists():
            return ["open", "-a", str(app_path)]
    return None


def cmd_open(args) -> int:
    audio = Path(args.audio)
    if not audio.exists():
        print(f"audio not found: {audio}", file=sys.stderr)
        return 1
    out_dir = _find_out_dir_for_audio(audio, getattr(args, "out_dir", None))
    sv = _find_sv_command()
    if sv is None:
        print("Sonic Visualiser not found. Install it first:", file=sys.stderr)
        print("  brew install --cask sonic-visualiser", file=sys.stderr)
        return 1

    # 如果之前因为 mp3 解码问题转码过，优先用转码后的 wav，保证 SV 也能打开
    sv_audio = prepared_audio_if_exists(audio, out_dir) or audio

    layers = []
    for rel in ("beats.csv", "chords.csv"):
        candidate = out_dir / rel
        if candidate.exists():
            layers.append(str(candidate))
    cmd = sv + [str(sv_audio)] + layers
    print(f"==> opening: {' '.join(cmd)}")
    subprocess.Popen(cmd)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="full analysis")
    p_run.add_argument("audio")
    p_run.add_argument("--artist")
    p_run.add_argument("--title")
    p_run.add_argument("--genius-token", default=None)
    p_run.add_argument("--device", default="cpu")
    p_run.set_defaults(func=cmd_run)

    p_struct = sub.add_parser("structure", help="run all-in-one-infer only")
    p_struct.add_argument("audio")
    p_struct.add_argument("--device", default="cpu")
    p_struct.set_defaults(func=cmd_structure)

    p_feat = sub.add_parser("features", help="beats/chords/melody")
    p_feat.add_argument("audio")
    p_feat.add_argument("--out-dir", default=None)
    p_feat.set_defaults(func=cmd_features)

    p_gen = sub.add_parser("genius", help="fetch Genius data")
    p_gen.add_argument("artist")
    p_gen.add_argument("title")
    p_gen.add_argument("--out-dir", default=None)
    p_gen.add_argument("--token", default=None)
    p_gen.set_defaults(func=cmd_genius)

    p_open = sub.add_parser("open", help="open audio + annotations in Sonic Visualiser")
    p_open.add_argument("audio")
    p_open.add_argument("--out-dir", default=None)
    p_open.set_defaults(func=cmd_open)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
