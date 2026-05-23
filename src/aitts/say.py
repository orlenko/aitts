"""aisay — macOS `say`-style TTS backed by OpenAI's gpt-4o-mini-tts.

Speaks the given text immediately via `afplay`, or writes audio to a file
with `-o`. Voice, tone (instructions), speed, format, and model are all
configurable.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import os
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from . import __version__
from .client import get_client
from .synthesis import (
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    FORMATS,
    VOICES,
    supports_instructions,
    synthesize,
)

DEFAULT_MAX_WAIT = 10.0


def _lock_path() -> Path:
    return Path(tempfile.gettempdir()) / f"aisay-{os.geteuid()}.lock"


def _play(path: str, args: argparse.Namespace) -> None:
    """Play `path` via afplay, serializing against other aisay processes.

    If `--no-lock` is set, skips serialization. Otherwise blocks on the
    playback lock and drops the message (without playing) if we waited
    longer than `--max-wait` seconds — the freshness TTL that prevents
    stale chatter from piling up when many agents speak at once.
    """
    if args.no_lock:
        subprocess.run(["afplay", path], check=False)
        return

    with _playback_lock() as waited:
        if waited > args.max_wait:
            if not args.quiet:
                print(
                    f"aisay: dropped (waited {waited:.1f}s in queue, "
                    f"--max-wait {args.max_wait:.1f}s)",
                    file=sys.stderr,
                )
            return
        subprocess.run(["afplay", path], check=False)


@contextmanager
def _playback_lock():
    """Block on a global per-user aisay playback lock.

    Yields the number of seconds spent waiting for the lock so the caller
    can decide whether to play or drop the message. Releases on context exit
    (including crash) — kernel-level via fcntl.flock.
    """
    fd = os.open(str(_lock_path()), os.O_CREAT | os.O_WRONLY, 0o600)
    start = time.monotonic()
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield time.monotonic() - start
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


class _ListVoicesAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        for v in VOICES:
            print(v)
        parser.exit(0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aisay",
        description="Speak text via OpenAI TTS (like macOS `say`).",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("text", nargs="*", help="Text to speak. If omitted, reads stdin.")
    p.add_argument("-v", "--voice", default=DEFAULT_VOICE, choices=VOICES,
                   help=f"Voice name (default: {DEFAULT_VOICE}).")
    p.add_argument("-i", "--instructions", default=None,
                   help="Tone/style prompt, e.g. 'calm, slow, British accent'. "
                        "Only supported by gpt-4o-mini-tts (and newer).")
    p.add_argument("-o", "--output", default=None,
                   help="Write audio to this file instead of playing.")
    p.add_argument("-s", "--speed", type=float, default=None,
                   help="Speech speed, 0.25-4.0 (default: 1.0).")
    p.add_argument("-f", "--format", default=None, choices=FORMATS,
                   help="Audio format. Defaults to mp3 for playback, or inferred "
                        "from -o extension when saving.")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL,
                   help=f"OpenAI TTS model (default: {DEFAULT_MODEL}).")
    p.add_argument("--list-voices", action=_ListVoicesAction,
                   help="Print supported voice names and exit.")
    p.add_argument("--max-wait", type=float, default=DEFAULT_MAX_WAIT,
                   help="Drop the speech if it waited longer than this many seconds in the "
                        f"playback queue (default: {DEFAULT_MAX_WAIT}). Prevents stale pile-ups "
                        "when many callers speak at once.")
    p.add_argument("--no-lock", action="store_true",
                   help="Skip the playback lock — do not serialize against other aisay processes.")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="Suppress informational messages on stderr (e.g. dropped-message notes).")
    return p


def read_text(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    if args.text:
        return " ".join(args.text).strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    parser.error("no text provided (pass as args or pipe via stdin)")


def resolve_output(args: argparse.Namespace) -> tuple[str, str, bool, bool]:
    """Return (path, fmt, play_after, cleanup)."""
    if args.output:
        path = os.path.expanduser(args.output)
        ext = os.path.splitext(path)[1].lstrip(".").lower()
        fmt = args.format or (ext if ext in FORMATS else "mp3")
        return path, fmt, False, False

    fmt = args.format or "mp3"
    fd, path = tempfile.mkstemp(suffix=f".{fmt}", prefix="aisay-")
    os.close(fd)
    return path, fmt, True, True


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    text = read_text(args, parser)
    if not text:
        parser.error("empty input")

    if args.instructions and not supports_instructions(args.model) and not args.quiet:
        print(
            f"aisay: warning — --instructions is ignored by model {args.model!r} "
            "(supported by gpt-4o-mini-tts and gpt-4o-tts).",
            file=sys.stderr,
        )

    client = get_client()
    out_path, fmt, play_after, cleanup = resolve_output(args)

    try:
        synthesize(
            text,
            out_path,
            client=client,
            model=args.model,
            voice=args.voice,
            format=fmt,
            speed=args.speed,
            instructions=args.instructions,
        )

        if play_after:
            _play(out_path, args)
        else:
            print(out_path)
    finally:
        if cleanup and os.path.exists(out_path):
            with contextlib.suppress(OSError):
                os.remove(out_path)

    return 0
