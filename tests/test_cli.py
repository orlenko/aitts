"""Tests for the aitts CLI surface and helpers that don't hit the network."""

from __future__ import annotations

import io
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

from aitts.cli import (
    DEFAULT_CONCURRENCY,
    _generate_chunks,
    _merge_parts,
    _resolve_input,
    _write_playlist,
    build_parser,
)
from aitts.synthesis import DEFAULT_MODEL, DEFAULT_VOICE

# ---------- parser shape ----------


def test_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["article.txt"])
    assert args.text_file == "article.txt"
    assert args.voice == DEFAULT_VOICE
    assert args.model == DEFAULT_MODEL
    assert args.instructions is None
    assert args.speed is None
    assert args.concurrency == DEFAULT_CONCURRENCY
    assert args.merge is False
    assert args.play is False


def test_parser_accepts_full_flag_set(tmp_path):
    parser = build_parser()
    args = parser.parse_args([
        "-v", "nova",
        "-m", "gpt-4o-mini-tts",
        "-i", "calm tone",
        "-s", "1.2",
        "--concurrency", "8",
        "--merge",
        "--play",
        "input.txt",
    ])
    assert args.voice == "nova"
    assert args.speed == 1.2
    assert args.concurrency == 8
    assert args.merge is True
    assert args.play is True
    assert args.instructions == "calm tone"


def test_parser_rejects_invalid_voice():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["-v", "not-a-voice", "input.txt"])


# ---------- _resolve_input ----------


def test_resolve_input_reads_file(tmp_path):
    p = tmp_path / "article.txt"
    p.write_text("hello world", encoding="utf-8")
    text, stem = _resolve_input(str(p), "2026-05-23-12-00")
    assert text == "hello world"
    assert stem == "article"


def test_resolve_input_handles_stdin(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("piped content\n"))
    text, stem = _resolve_input("-", "2026-05-23-12-00")
    assert text == "piped content\n"
    assert stem == "stdin-2026-05-23-12-00"


def test_resolve_input_stdin_empty_raises(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("   \n"))
    with pytest.raises(RuntimeError, match="empty input"):
        _resolve_input("-", "ts")


def test_resolve_input_url_calls_fetch(monkeypatch):
    monkeypatch.setattr("aitts.cli.fetch_url_text", lambda url: f"fetched: {url}")
    text, stem = _resolve_input("https://example.com/post", "ts")
    assert text == "fetched: https://example.com/post"
    assert stem == "https-example-com-post"


# ---------- _generate_chunks (no real API) ----------


def test_generate_chunks_writes_files_in_order(tmp_path):
    chunks = ["one", "two", "three"]
    written: list[Path] = []

    def fake_synthesize(text, out_path, **kwargs):
        Path(out_path).write_bytes(b"\x00\x01")
        written.append(Path(out_path))

    with patch("aitts.cli.synthesize", side_effect=fake_synthesize):
        names = _generate_chunks(
            chunks, tmp_path, client=None, voice="marin", model=DEFAULT_MODEL,
            instructions=None, speed=None, concurrency=2,
        )

    assert names == ["part01.mp3", "part02.mp3", "part03.mp3"]
    assert all((tmp_path / n).exists() for n in names)


def test_generate_chunks_skips_failures(tmp_path, capsys):
    chunks = ["good", "bad", "good"]

    def fake_synthesize(text, out_path, **kwargs):
        if text == "bad":
            raise RuntimeError("boom")
        Path(out_path).write_bytes(b"\x00")

    with patch("aitts.cli.synthesize", side_effect=fake_synthesize):
        names = _generate_chunks(
            chunks, tmp_path, client=None, voice="marin", model=DEFAULT_MODEL,
            instructions=None, speed=None, concurrency=1,
        )

    assert names == ["part01.mp3", "part03.mp3"]
    captured = capsys.readouterr()
    assert "Failed chunk 2" in captured.err


# ---------- _write_playlist ----------


def test_write_playlist(tmp_path):
    playlist = _write_playlist(tmp_path, ["part01.mp3", "part02.mp3"])
    assert playlist == tmp_path / "playlist.m3u"
    assert playlist.read_text(encoding="utf-8") == "part01.mp3\npart02.mp3\n"


# ---------- _merge_parts ----------


def test_merge_parts_skips_when_ffmpeg_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("aitts.cli.shutil.which", lambda name: None)
    result = _merge_parts(tmp_path, ["part01.mp3"])
    assert result is None
    assert "ffmpeg not on PATH" in capsys.readouterr().err


def test_merge_parts_skips_when_no_parts(tmp_path, monkeypatch):
    monkeypatch.setattr("aitts.cli.shutil.which", lambda name: "/usr/bin/ffmpeg")
    assert _merge_parts(tmp_path, []) is None


# ---------- error UX ----------


def test_main_returns_1_and_no_traceback_on_runtime_error(monkeypatch, capsys):
    from aitts.cli import main

    def boom(args):
        raise RuntimeError("HTTP 403 fetching https://example.com/walled")

    monkeypatch.setattr("aitts.cli.convert_to_speech", boom)
    monkeypatch.setattr("sys.argv", ["aitts", "https://example.com/walled"])
    rc = main()
    err = capsys.readouterr().err
    assert rc == 1
    assert "aitts: HTTP 403" in err
    assert "Traceback" not in err


def test_download_html_uses_urllib_fallback_when_trafilatura_returns_none(monkeypatch):

    from aitts.cli import _download_html

    monkeypatch.setattr("aitts.cli.trafilatura.fetch_url", lambda url: None)

    class FakeResponse:
        headers = type("H", (), {"get_content_charset": lambda self: "utf-8"})()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"<html><body>fallback content</body></html>"

    monkeypatch.setattr(
        "aitts.cli.urllib.request.urlopen",
        lambda req, timeout=None: FakeResponse(),
    )
    html = _download_html("https://example.com/blocked")
    assert "fallback content" in html


def test_download_html_raises_clean_http_error(monkeypatch):
    from aitts.cli import _download_html

    monkeypatch.setattr("aitts.cli.trafilatura.fetch_url", lambda url: None)

    def raise_403(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr("aitts.cli.urllib.request.urlopen", raise_403)
    with pytest.raises(RuntimeError, match="HTTP 403"):
        _download_html("https://example.com/walled")
