"""Shared TTS synthesis: one place that calls the OpenAI speech API."""

from __future__ import annotations

from pathlib import Path

from openai import OpenAI

# https://platform.openai.com/docs/guides/text-to-speech
VOICES = [
    "alloy", "ash", "ballad", "cedar", "coral", "echo",
    "fable", "marin", "nova", "onyx", "sage", "shimmer", "verse",
]
FORMATS = ["mp3", "opus", "aac", "flac", "wav", "pcm"]
DEFAULT_MODEL = "gpt-4o-mini-tts"
DEFAULT_VOICE = "marin"  # OpenAI recommends marin/cedar for quality
INSTRUCTIONS_CAPABLE_PREFIXES = ("gpt-4o-mini-tts", "gpt-4o-tts")


def supports_instructions(model: str) -> bool:
    return model.startswith(INSTRUCTIONS_CAPABLE_PREFIXES)


def synthesize(
    text: str,
    out_path: str | Path,
    *,
    client: OpenAI,
    model: str = DEFAULT_MODEL,
    voice: str = DEFAULT_VOICE,
    format: str = "mp3",
    speed: float | None = None,
    instructions: str | None = None,
) -> None:
    """Generate audio for `text` and write it to `out_path`.

    Streams chunks from the OpenAI API and writes them in-place; uses the
    non-deprecated `iter_bytes()` path so we don't depend on `stream_to_file`.
    """
    kwargs: dict = {
        "model": model,
        "voice": voice,
        "input": text,
        "response_format": format,
    }
    if instructions and supports_instructions(model):
        kwargs["instructions"] = instructions
    if speed is not None:
        kwargs["speed"] = speed

    with (
        client.audio.speech.with_streaming_response.create(**kwargs) as response,
        open(out_path, "wb") as fh,
    ):
        for chunk in response.iter_bytes():
            fh.write(chunk)
