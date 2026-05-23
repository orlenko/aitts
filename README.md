# aitts

OpenAI-backed text-to-speech CLIs for the terminal.

- **`aisay`** — speak short text immediately, like macOS `say` but with OpenAI voices, tone instructions, and concurrency-safe playback.
- **`aitts`** — turn a long text file or web article into an mp3 playlist you can queue in any m3u player.

> **Platform:** macOS only for now (`aisay` plays via `afplay`). Cross-platform playback is on the roadmap — see [#1](https://github.com/orlenko/aitts/issues). `-o` output works everywhere.

## Install

```sh
# Recommended: isolated install via pipx or uv
pipx install aitts
uv tool install aitts

# Or plain pip
pip install aitts
```

Both `aisay` and `aitts` land on your `PATH`. Set `OPENAI_API_KEY` in your environment or place it in a `.env` file in the working directory.

## `aisay` — short-form, plays immediately

```sh
aisay "Hello world"
aisay -v nova -i "calm, slow, British accent" "Welcome back."
echo "piped text works too" | aisay
aisay -o out.mp3 "Save instead of play"
aisay -s 1.2 "Faster, please"
aisay --list-voices
```

### Flags

| Flag | Description |
|------|-------------|
| `-v, --voice` | Voice name (default: `marin`). See `--list-voices`. |
| `-i, --instructions` | Free-form tone/style prompt. `gpt-4o-mini-tts` and newer only. |
| `-s, --speed` | Speech speed, 0.25–4.0. |
| `-f, --format` | `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm`. |
| `-o, --output` | Write to file instead of playing. |
| `-m, --model` | OpenAI TTS model (default: `gpt-4o-mini-tts`). |
| `--list-voices` | Print supported voice names and exit. |
| `--max-wait` | Drop the message if it waited longer than this many seconds in the playback queue (default: 10). |
| `--no-lock` | Skip the playback lock entirely. |
| `-q, --quiet` | Suppress informational messages on stderr. |

### Concurrency

When many callers invoke `aisay` at once (say, twenty `claude` sessions each running a "speak the response" hook), playback is serialized via a per-user `flock` on `$TMPDIR/aisay-<uid>.lock`. Audio generation still happens in parallel — only `afplay` is serialized.

If a message has been waiting in the queue longer than `--max-wait` seconds by the time its turn comes, it's silently dropped (with a one-line note to stderr, unless `--quiet`) rather than played stale. Tune higher to hear more, lower to drop sooner, or pass `--no-lock` to bypass.

## `aitts` — long-form, writes a playlist

```sh
aitts samples/english-sonnet.txt
aitts https://example.com/long-article --play
```

Output lands in `${XDG_DATA_HOME:-~/.local/share}/aitts/<slug>/<timestamp>/`, containing one `partNN.mp3` per chunk plus a `playlist.m3u`. Override the base directory with `AITTS_DATA_DIR=/some/path`.

`--play` opens the playlist in VLC on macOS.

## Environment

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required. Read from env or a `.env` file in the working directory. |
| `AITTS_DATA_DIR` | Override the output base directory for `aitts`. |
| `XDG_DATA_HOME` | Honored when `AITTS_DATA_DIR` is unset. |

## Develop

```sh
git clone https://github.com/orlenko/aitts
cd aitts
uv sync
uv run aisay "hello"
uv run pytest
uv run ruff check .
```

To install your local checkout as the global tool:

```sh
uv tool install . --reinstall --no-cache
```

## License

MIT — see [LICENSE](LICENSE).
