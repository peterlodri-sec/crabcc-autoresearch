#!/usr/bin/env python3
"""
Patches autoresearch's main_loop.py to use OpenRouter instead of the
Anthropic SDK. Safe to run multiple times (idempotent).

Usage:
    python patch_llm.py [path/to/main_loop.py]   # default: ./main_loop.py
"""

import sys
from pathlib import Path

MARKER = "# patched: openrouter"
DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

IMPORT_REPLACEMENT = f"""\
{MARKER}
import os as _os
from openai import OpenAI as _OAI

def _make_client():
    _client = _OAI(
        base_url="{OPENROUTER_BASE}",
        api_key=_os.environ.get("OPENROUTER_API_KEY", ""),
        default_headers={{
            "HTTP-Referer": "https://research.crabcc.app",
            "X-Title": "crabcc-autoresearch",
            "X-crabcc-run": _os.environ.get("RUN_ID", "unnamed"),
            "anthropic-beta": "prompt-caching-2024-07-31",
        }},
    )
    try:
        if _os.environ.get("LANGSMITH_API_KEY"):
            from langsmith.wrappers import wrap_openai as _wrap
            _os.environ.setdefault("LANGSMITH_PROJECT", "crabcc-autoresearch")
            return _wrap(_client)
    except ImportError:
        pass
    return _client
"""

REPLACEMENTS: list[tuple[str, str]] = [
    # import
    ("import anthropic", IMPORT_REPLACEMENT),
    # client instantiation
    ("anthropic.Anthropic()", "_make_client()"),
    ("anthropic.Anthropic()", "_make_client()"),
    # API call
    ("client.messages.create(", "client.chat.completions.create("),
    # model name — pin to env var so it's swappable at runtime
    (
        'model="claude-opus-4-5"',
        f'model=_os.environ.get("LLM_MODEL", "{DEFAULT_MODEL}")',
    ),
    (
        'model="claude-sonnet-4-5"',
        f'model=_os.environ.get("LLM_MODEL", "{DEFAULT_MODEL}")',
    ),
    (
        'model="claude-3-5-sonnet-20241022"',
        f'model=_os.environ.get("LLM_MODEL", "{DEFAULT_MODEL}")',
    ),
    # response access
    ("message.content[0].text", "message.choices[0].message.content"),
    (".content[0].text", ".choices[0].message.content"),
]


def patch(path: Path) -> None:
    src = path.read_text()

    if MARKER in src:
        print(f"[patch_llm] {path} already patched — skipping")
        return

    for old, new in REPLACEMENTS:
        src = src.replace(old, new)

    path.write_text(src)
    print(f"[patch_llm] patched {path}")


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else "main_loop.py"
    target = Path(raw).resolve()
    if target.suffix != ".py" or ".." in Path(raw).parts:
        print(f"[patch_llm] invalid target path: {raw}")
        sys.exit(1)
    if not target.exists():
        print(f"[patch_llm] {target} not found — skipping (not yet cloned?)")
        sys.exit(0)
    patch(target)
