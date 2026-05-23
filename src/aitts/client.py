"""Shared OpenAI client construction with a friendly missing-key error."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

_MISSING_KEY_MSG = (
    "OPENAI_API_KEY is not set.\n"
    "Set it in your environment or create a .env file in the working directory:\n"
    "    export OPENAI_API_KEY=sk-...\n"
    "Get a key at https://platform.openai.com/api-keys"
)


def get_client() -> OpenAI:
    """Return a configured OpenAI client, or exit 2 with a friendly message."""
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print(_MISSING_KEY_MSG, file=sys.stderr)
        raise SystemExit(2)
    return OpenAI(max_retries=3)
