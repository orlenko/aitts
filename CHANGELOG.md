# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] — 2026-05-22

First public release on PyPI.

### Added
- `aisay` — `say`-style TTS CLI backed by OpenAI's `gpt-4o-mini-tts`.
  - Voice, model, tone (`--instructions`), speed, and audio format flags.
  - `--list-voices` for discoverability.
  - Per-user `flock`-based playback serialization so concurrent callers don't talk over each other.
  - `--max-wait` freshness TTL — drops messages that have been waiting too long, keeping audio responsive.
  - `--quiet` for silent operation in hook/scripting contexts.
  - `--no-lock` bypass for one-off use.
- `aitts` — long-form text or URL to mp3 playlist (`.m3u`) generator.
  - Reads from a local file or extracts a web article via newspaper3k.
  - Splits text on sentence/whitespace boundaries with hard-cut fallback.
  - XDG-aware output dir, overridable via `AITTS_DATA_DIR`.
- Friendly error when `OPENAI_API_KEY` is missing.
- Pytest suite covering CLI helpers, playback lock semantics, and text splitting.

### Internal
- Shared `client.py` and `synthesis.py` modules consolidate OpenAI plumbing.
- Replaced deprecated `response.stream_to_file()` with the modern `iter_bytes()` pattern.
