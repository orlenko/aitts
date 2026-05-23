"""Tests for aisay CLI helpers — read_text, resolve_output, lock semantics."""

from __future__ import annotations

import io
import os
import threading
import time
from types import SimpleNamespace

import pytest

from aitts.say import (
    DEFAULT_MAX_WAIT,
    _lock_path,
    _playback_lock,
    build_parser,
    read_text,
    resolve_output,
)

# ---------- read_text ----------


def test_read_text_uses_positional_args():
    parser = build_parser()
    args = parser.parse_args(["hello", "world"])
    assert read_text(args, parser) == "hello world"


def test_read_text_reads_stdin_when_no_args(monkeypatch):
    parser = build_parser()
    args = parser.parse_args([])
    monkeypatch.setattr("sys.stdin", io.StringIO("from stdin\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    # io.StringIO has no isatty? It does — returns False by default. Good.
    assert read_text(args, parser) == "from stdin"


def test_read_text_errors_when_nothing_provided(monkeypatch):
    parser = build_parser()
    args = parser.parse_args([])
    # Simulate a real TTY: isatty() returns True so we hit parser.error.
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
    with pytest.raises(SystemExit):
        read_text(args, parser)


# ---------- resolve_output ----------


def test_resolve_output_default_is_temp_mp3_to_play(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    parser = build_parser()
    args = parser.parse_args(["hello"])
    path, fmt, play_after, cleanup = resolve_output(args)
    try:
        assert play_after is True
        assert cleanup is True
        assert fmt == "mp3"
        assert path.endswith(".mp3")
        assert os.path.exists(path)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_resolve_output_format_inferred_from_extension(tmp_path):
    parser = build_parser()
    out = tmp_path / "speech.flac"
    args = parser.parse_args(["-o", str(out), "hello"])
    path, fmt, play_after, cleanup = resolve_output(args)
    assert path == str(out)
    assert fmt == "flac"
    assert play_after is False
    assert cleanup is False


def test_resolve_output_explicit_format_overrides_extension(tmp_path):
    parser = build_parser()
    out = tmp_path / "speech.flac"
    args = parser.parse_args(["-f", "wav", "-o", str(out), "hello"])
    _, fmt, _, _ = resolve_output(args)
    assert fmt == "wav"


def test_resolve_output_unknown_extension_defaults_to_mp3(tmp_path):
    parser = build_parser()
    out = tmp_path / "speech.weird"
    args = parser.parse_args(["-o", str(out), "hello"])
    _, fmt, _, _ = resolve_output(args)
    assert fmt == "mp3"


# ---------- _playback_lock ----------


def test_playback_lock_first_acquirer_waits_near_zero(monkeypatch, tmp_path):
    monkeypatch.setattr("aitts.say._lock_path", lambda: tmp_path / "test.lock")
    with _playback_lock() as waited:
        assert waited < 0.1


def test_playback_lock_serializes_concurrent_holders(monkeypatch, tmp_path):
    """Second acquirer should wait at least as long as the first holds."""
    monkeypatch.setattr("aitts.say._lock_path", lambda: tmp_path / "test.lock")

    hold_seconds = 0.3
    second_waited: list[float] = []
    first_acquired = threading.Event()

    def hold_first():
        with _playback_lock() as waited:
            assert waited < 0.1
            first_acquired.set()
            time.sleep(hold_seconds)

    def take_second():
        first_acquired.wait()
        with _playback_lock() as waited:
            second_waited.append(waited)

    t1 = threading.Thread(target=hold_first)
    t2 = threading.Thread(target=take_second)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(second_waited) == 1
    # Second waiter waited until first released; should be close to hold_seconds.
    assert second_waited[0] >= hold_seconds * 0.5


def test_lock_path_is_per_user(monkeypatch):
    monkeypatch.setattr("os.geteuid", lambda: 12345)
    p = _lock_path()
    assert "aisay-12345" in p.name


# ---------- parser shape ----------


def test_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["hello"])
    assert args.voice == "marin"
    assert args.model == "gpt-4o-mini-tts"
    assert args.max_wait == DEFAULT_MAX_WAIT
    assert args.no_lock is False
    assert args.quiet is False


def test_parser_rejects_unknown_voice():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["-v", "definitely-not-a-voice", "hello"])
