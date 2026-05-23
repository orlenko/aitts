"""Path helpers — XDG-aware data directory with env-var override."""

from __future__ import annotations

import os
from pathlib import Path


def _expand(path: str | os.PathLike[str]) -> Path:
    return Path(os.fspath(path)).expanduser().resolve()


def data_dir() -> Path:
    """Directory where aitts writes audio + playlists.

    Resolution order: $AITTS_DATA_DIR, then $XDG_DATA_HOME/aitts, then
    ~/.local/share/aitts. Created on first call.
    """
    override = os.getenv("AITTS_DATA_DIR")
    if override:
        d = _expand(override)
    else:
        xdg = os.getenv("XDG_DATA_HOME")
        base = _expand(xdg) if xdg else _expand("~/.local/share")
        d = base / "aitts"
    d.mkdir(parents=True, exist_ok=True)
    return d
