"""aitts — long-form text or URL → OpenAI TTS mp3 playlist."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import trafilatura
from slugify import slugify
from trafilatura.metadata import extract_metadata

from . import __version__
from .client import get_client
from .paths import _expand, data_dir
from .synthesis import DEFAULT_MODEL, DEFAULT_VOICE, VOICES, synthesize

DEFAULT_CONCURRENCY = 4


def split_text(text: str, max_length: int = 4000) -> list[str]:
    """Split `text` into chunks <= max_length, preferring sentence boundaries.

    Falls back to whitespace, then hard cut, when no sentence-ending
    punctuation is found in the lookback window.
    """
    chunks: list[str] = []
    text = text.strip()
    while len(text) > max_length:
        split_index = max_length
        while split_index > 0 and not re.search(
            r"[.!?]\s", text[split_index - 1 : split_index + 1]
        ):
            split_index -= 1
        if split_index == 0:
            ws = text.rfind(" ", 0, max_length)
            split_index = ws if ws > 0 else max_length
        chunks.append(text[:split_index].strip())
        text = text[split_index:].strip()
    if text:
        chunks.append(text)
    return chunks


def fetch_url_text(url: str) -> str:
    """Download `url` and extract main article text (title + body)."""
    html = trafilatura.fetch_url(url)
    if not html:
        raise RuntimeError(f"Failed to download {url}")
    body = trafilatura.extract(
        html, url=url, favor_precision=True, include_comments=False
    )
    if not body:
        raise RuntimeError(f"Could not extract readable text from {url}")
    metadata = extract_metadata(html, default_url=url)
    title = metadata.title if metadata else None
    return f"{title}\n\n{body}" if title else body


def _resolve_input(arg: str, timestamp: str) -> tuple[str, str]:
    """Return (plain_text, stem) for a URL, file path, or '-' (stdin)."""
    if arg == "-":
        text = sys.stdin.read()
        if not text.strip():
            raise RuntimeError("empty input on stdin")
        return text, f"stdin-{timestamp}"
    if arg.startswith(("http://", "https://")):
        return fetch_url_text(arg), slugify(arg)
    text_path = _expand(arg)
    return text_path.read_text(encoding="utf-8"), text_path.stem


def _save_source(plain_text: str, output_dir: Path, stem: str, original_arg: str) -> None:
    """Persist the source text alongside the audio for reproducibility."""
    if original_arg == "-" or original_arg.startswith(("http://", "https://")):
        (output_dir / f"{stem}.txt").write_text(plain_text, encoding="utf-8")
    else:
        shutil.copy(_expand(original_arg), output_dir)


def _generate_chunks(
    chunks: list[str],
    output_dir: Path,
    *,
    client,
    voice: str,
    model: str,
    instructions: str | None,
    speed: float | None,
    concurrency: int,
) -> list[str]:
    """Generate audio for each chunk in parallel, return part filenames in order.

    Each chunk's filename is computed up-front so playlist order is deterministic
    regardless of completion order. Failed chunks are reported but do not abort
    the others — the playlist will list only the successful parts.
    """
    part_names: list[str | None] = [None] * len(chunks)

    def _one(idx: int, chunk: str) -> tuple[int, str]:
        part_filename = f"part{idx + 1:02d}.mp3"
        synthesize(
            chunk,
            output_dir / part_filename,
            client=client,
            model=model,
            voice=voice,
            format="mp3",
            speed=speed,
            instructions=instructions,
        )
        return idx, part_filename

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(_one, i, c): i for i, c in enumerate(chunks)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                _, name = fut.result()
                part_names[idx] = name
                print(f"Saved {name} ({idx + 1}/{len(chunks)})")
            except Exception as e:
                print(f"Failed chunk {idx + 1}: {e}", file=sys.stderr)

    return [n for n in part_names if n is not None]


def _write_playlist(output_dir: Path, part_names: list[str]) -> Path:
    playlist = output_dir / "playlist.m3u"
    with open(playlist, "w", encoding="utf-8") as fh:
        for name in part_names:
            fh.write(f"{name}\n")
    return playlist


def _merge_parts(output_dir: Path, part_names: list[str]) -> Path | None:
    """Concatenate parts into merged.mp3 via ffmpeg. Returns path or None on skip."""
    if not shutil.which("ffmpeg"):
        print("aitts: ffmpeg not on PATH — skipping --merge.", file=sys.stderr)
        return None
    if not part_names:
        return None
    concat_list = output_dir / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{name}'" for name in part_names), encoding="utf-8"
    )
    merged = output_dir / "merged.mp3"
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(concat_list), "-c", "copy", str(merged)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"aitts: ffmpeg failed: {result.stderr.strip()}", file=sys.stderr)
        return None
    print(f"Merged into {merged}")
    return merged


def _open_playlist(playlist: Path) -> None:
    """Open the playlist in VLC if available, falling back to system default."""
    if shutil.which("vlc"):
        subprocess.Popen(["vlc", str(playlist)])
        return
    if sys.platform == "darwin":
        subprocess.run(["open", "-a", "VLC", str(playlist)], check=False)
        return
    print(
        "aitts: --play needs VLC on PATH (or VLC.app on macOS). "
        f"Open {playlist} manually.",
        file=sys.stderr,
    )


def convert_to_speech(args: argparse.Namespace) -> None:
    client = get_client()
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")

    plain_text, stem = _resolve_input(args.text_file, timestamp)
    output_dir = data_dir() / stem / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    _save_source(plain_text, output_dir, stem, args.text_file)

    chunks = split_text(plain_text)
    print(f"Generating {len(chunks)} chunk(s) at concurrency={args.concurrency}...")

    part_names = _generate_chunks(
        chunks,
        output_dir,
        client=client,
        voice=args.voice,
        model=args.model,
        instructions=args.instructions,
        speed=args.speed,
        concurrency=args.concurrency,
    )

    if len(part_names) != len(chunks):
        print(
            f"aitts: {len(chunks) - len(part_names)} chunk(s) failed — "
            "playlist contains successful parts only.",
            file=sys.stderr,
        )

    playlist = _write_playlist(output_dir, part_names)
    print(f"Playlist saved at: {playlist}")

    if args.merge:
        _merge_parts(output_dir, part_names)

    if args.play:
        _open_playlist(playlist)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aitts",
        description="Convert long text, a file, or a URL into an OpenAI-TTS mp3 playlist.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "text_file",
        help="Path to a text file, a URL, or '-' to read from stdin.",
    )
    p.add_argument("-v", "--voice", default=DEFAULT_VOICE, choices=VOICES,
                   help=f"Voice name (default: {DEFAULT_VOICE}).")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL,
                   help=f"OpenAI TTS model (default: {DEFAULT_MODEL}).")
    p.add_argument("-i", "--instructions", default=None,
                   help="Tone/style prompt. Only supported by gpt-4o-mini-tts (and newer).")
    p.add_argument("-s", "--speed", type=float, default=None,
                   help="Speech speed, 0.25-4.0.")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                   help=f"Parallel chunk generation (default: {DEFAULT_CONCURRENCY}).")
    p.add_argument("--merge", action="store_true",
                   help="After generation, concat parts into merged.mp3 via ffmpeg.")
    p.add_argument("--play", action="store_true",
                   help="Open the generated playlist in VLC (or system default).")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")
    convert_to_speech(args)
    return 0
