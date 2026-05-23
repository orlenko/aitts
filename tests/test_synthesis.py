"""Tests for the synthesis helpers — they don't call the API."""

from __future__ import annotations

from aitts.synthesis import (
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    FORMATS,
    VOICES,
    supports_instructions,
)


def test_default_voice_is_supported():
    assert DEFAULT_VOICE in VOICES


def test_formats_includes_mp3():
    assert "mp3" in FORMATS


def test_supports_instructions_gpt4o():
    assert supports_instructions(DEFAULT_MODEL) is True
    assert supports_instructions("gpt-4o-tts") is True


def test_does_not_support_instructions_for_tts1():
    assert supports_instructions("tts-1") is False
    assert supports_instructions("tts-1-hd") is False
