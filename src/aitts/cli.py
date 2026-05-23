"""aitts — long-form text or URL → OpenAI TTS mp3 playlist."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from datetime import datetime

from newspaper import Article
from slugify import slugify

from . import __version__
from .client import get_client
from .paths import _expand, data_dir
from .synthesis import DEFAULT_MODEL, DEFAULT_VOICE, synthesize


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
            # No sentence boundary; try a whitespace break instead.
            ws = text.rfind(" ", 0, max_length)
            split_index = ws if ws > 0 else max_length
        chunks.append(text[:split_index].strip())
        text = text[split_index:].strip()
    if text:
        chunks.append(text)
    return chunks


def fetch_url_text(url: str) -> str:
    article = Article(url)
    article.download()
    article.parse()
    return article.title + "\n\n" + article.text


def convert_to_speech(text_file_arg: str, play: bool = False) -> None:
    client = get_client()
    current_datetime = datetime.now().strftime("%Y-%m-%d-%H-%M")

    if text_file_arg.startswith(("http://", "https://")):
        url = text_file_arg
        stem = slugify(url)
        output_dir = data_dir() / stem / current_datetime
        output_dir.mkdir(parents=True, exist_ok=True)
        plain_text = fetch_url_text(url)
        text_path = output_dir / f"{stem}.txt"
        text_path.write_text(plain_text, encoding="utf-8")
    else:
        text_path = _expand(text_file_arg)
        plain_text = text_path.read_text(encoding="utf-8")
        stem = text_path.stem
        output_dir = data_dir() / stem / current_datetime
        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(text_path, output_dir)

    chunks = split_text(plain_text)
    playlist_file = output_dir / "playlist.m3u"

    with open(playlist_file, "w", encoding="utf-8") as playlist:
        for i, chunk in enumerate(chunks, start=1):
            part_filename = f"part{i:02d}.mp3"
            part_path = output_dir / part_filename
            max_retries = 3
            for retry in range(max_retries):
                try:
                    synthesize(
                        chunk,
                        part_path,
                        client=client,
                        model=DEFAULT_MODEL,
                        voice=DEFAULT_VOICE,
                        format="mp3",
                    )
                    print(f"Saved file {part_filename}")
                    playlist.write(f"{part_filename}\n")
                    break
                except Exception as e:
                    print(f"Error converting chunk {i}: {e}")
                    if retry < max_retries - 1:
                        print(f"Retrying... ({retry + 1}/{max_retries})")
                    else:
                        print(f"Failed to convert chunk {i} after {max_retries} retries")
                        raise

    print(f"Playlist saved at: {playlist_file}")

    if play:
        subprocess.run(["open", "-a", "VLC", str(playlist_file)], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="aitts",
        description="Convert long text or a URL into a TTS mp3 playlist.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("text_file", help="Path to a text file or a URL")
    parser.add_argument("--play", action="store_true", help="Open the generated playlist in VLC")

    args = parser.parse_args()
    convert_to_speech(args.text_file, args.play)
    return 0
