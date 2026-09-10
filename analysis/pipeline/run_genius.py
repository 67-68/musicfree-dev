"""Fetch song metadata and lyrics from Genius (best-effort, cached)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def run_genius(
    out_dir: Path,
    *,
    artist: str,
    title: str,
    token: Optional[str] = None,
) -> Optional[Path]:
    """Pull Genius data into genius.json. Returns path or None."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "genius.json"
    if target.exists():
        print(f"  [genius] cache hit: {target}")
        return target

    token = token or _env_token()
    if not token:
        print("  [genius] no GENIUS_ACCESS_TOKEN provided; skipping Genius fetch")
        return None

    data: Dict[str, Any] = {
        "artist": artist,
        "title": title,
        "source_url": None,
        "lyrics": None,
        "sections": [],
        "error": None,
    }

    try:
        import lyricsgenius

        genius = lyricsgenius.Genius(token, verbose=False, remove_section_headers=False)
        song = genius.search_song(title, artist)
        if song is None:
            data["error"] = "song not found on Genius"
        else:
            data["source_url"] = getattr(song, "url", None)
            data["lyrics"] = getattr(song, "lyrics", None)
            sections = getattr(song, "sections", None)
            if isinstance(sections, list) and sections:
                data["sections"] = sections
            else:
                data["sections"] = _sections_from_lyrics(data["lyrics"])
    except Exception as exc:
        print(f"  [genius] lyricsgenius failed: {exc}")
        data["error"] = str(exc)

    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _env_token() -> Optional[str]:
    import os

    return os.environ.get("GENIUS_ACCESS_TOKEN") or os.environ.get("GENIUS_TOKEN")


def _sections_from_lyrics(lyrics: Optional[str]) -> list:
    """Fallback: split lyrics text on [Section] markers."""
    if not lyrics:
        return []
    sections = []
    current_name = "Lyrics"
    current_lines = []
    for line in lyrics.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and len(stripped) < 80:
            if current_lines:
                sections.append({"name": current_name, "text": "\n".join(current_lines).strip()})
            current_name = stripped[1:-1]
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append({"name": current_name, "text": "\n".join(current_lines).strip()})
    return sections


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Fetch song data from Genius")
    parser.add_argument("--artist", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()
    result = run_genius(Path(args.out_dir), artist=args.artist, title=args.title, token=args.token)
    print(result)
