"""Audio input preparation.

Some formats (notably mp3 on certain libsndfile/torchaudio builds) fail to
decode in the all-in-one-infer / demucs pipeline.  When that happens we
transcode the source to a plain PCM wav once and let the rest of the
pipeline work on the wav.

The original user-visible ``track.path`` is kept by the caller, so this
module only returns the path that should be fed to the analysis steps.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


# 这些格式 libsndfile 通常能稳定解码，直接交给 all-in-one-infer。
# 其他格式（尤其 mp3）在部分 libsndfile/torchaudio 构建上会解到一半失败，
# 统一转成 PCM wav，转码结果缓存在 out_dir/source.wav。
_SAFE_EXTS = {
    ".wav",
    ".wave",
    ".flac",
    ".aif",
    ".aiff",
    ".au",
    ".caf",
    ".w64",
    ".ogg",
    ".oga",
    ".opus",
}


def _soundfile_small_readable(audio_path: Path) -> bool:
    try:
        import soundfile as sf

        with sf.SoundFile(str(audio_path)) as handle:
            handle.read(4096, dtype="int16", always_2d=True)
        return True
    except Exception:
        return False


def _needs_transcode(audio_path: Path) -> bool:
    if audio_path.suffix.lower() not in _SAFE_EXTS:
        return True
    return not _soundfile_small_readable(audio_path)


def _transcode_with_ffmpeg(src: Path, dst: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    cmd = [
        ffmpeg,
        "-v",
        "error",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "2",
        "-ar",
        "44100",
        "-c:a",
        "pcm_s16le",
        str(dst),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except Exception:
        return False
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        return False
    return True


def _transcode_with_librosa(src: Path, dst: Path) -> bool:
    try:
        import librosa
        import numpy as np
        import soundfile as sf

        y, sr = librosa.load(str(src), sr=44100, mono=False)
        y = np.asarray(y)
        if y.ndim == 1:
            y = y.reshape(1, -1)
        sf.write(str(dst), y.T, sr, subtype="PCM_16")
        return dst.exists() and dst.stat().st_size > 0
    except Exception:
        return False


def prepare_audio(
    audio_path: Path,
    out_dir: Path,
    *,
    force: bool = False,
) -> Path:
    """Return a path that all-in-one-infer can decode.

    - If the source is already soundfile-readable, return it unchanged.
    - Otherwise transcode to ``<out_dir>/source.wav`` (cached).
    """
    audio_path = Path(audio_path).resolve()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not force and not _needs_transcode(audio_path):
        return audio_path

    dst = out_dir / "source.wav"
    if not force and dst.exists() and dst.stat().st_mtime >= audio_path.stat().st_mtime:
        return dst

    if dst.exists():
        try:
            dst.unlink()
        except Exception:
            pass

    if _transcode_with_ffmpeg(audio_path, dst):
        print(f"  [audio] 已转码为 wav（ffmpeg）：{dst}")
        return dst

    if _transcode_with_librosa(audio_path, dst):
        print(f"  [audio] 已转码为 wav（librosa）：{dst}")
        return dst

    raise RuntimeError(
        f"无法解码音频：{audio_path}。请安装 ffmpeg，或把文件转成 wav/flac 后重试。"
    )


def prepared_audio_if_exists(audio_path: Path, out_dir: Path) -> Optional[Path]:
    """Return the cached transcoded wav if present, otherwise None."""
    dst = Path(out_dir) / "source.wav"
    return dst if dst.exists() else None
