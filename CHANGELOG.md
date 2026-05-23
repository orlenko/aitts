# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `aitts` no longer dumps a traceback when a URL can't be fetched — emits a one-line error (e.g. `aitts: HTTP 403 fetching <url>`) and exits 1.
- URL downloads now fall back to a browser-shaped User-Agent when trafilatura's default UA is rejected. Paywalled / JS-rendered pages still fail, but with a clean message pointing at the cause.

### Changed
- `aitts` now uses [trafilatura](https://github.com/adbar/trafilatura) for URL article extraction instead of the unmaintained `newspaper3k`. Drops `lxml_html_clean` (transitive workaround) along with it.
- `aitts` chunk generation runs in parallel (default 4 workers, configurable via `--concurrency`). Failed chunks no longer abort the whole run — the playlist is written with successful parts and a stderr note about misses.
- Removed the manual retry loop in `aitts`; the OpenAI client now retries on 5xx/429 with `max_retries=3` via the SDK.
- `aitts --play` is now portable: prefers `vlc` from `PATH`, falls back to `VLC.app` on macOS.

### Added
- `aitts` matches `aisay`'s flag set: `-v/--voice`, `-m/--model`, `-i/--instructions`, `-s/--speed`.
- `aitts -` reads from stdin and tags the output dir with a `stdin-<timestamp>` stem.
- `aitts --merge` concatenates parts into a single `merged.mp3` via `ffmpeg` (when available).

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
