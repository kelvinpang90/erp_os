"""
Prompt template loader.

Prompts live in ``backend/app/prompts/*.yaml`` and are loaded once at startup
into an in-process cache. Each YAML defines:

    version: "1.0.0"
    model: "claude-sonnet-4-6"
    temperature: 0.0
    max_tokens: 2048
    system: |
      ...system instructions...
    user_template: |
      ...user message; may contain {placeholders} resolved by .render(...)

Why YAML and not JSON? Multiline strings are first-class. Why not plain Python
constants? Versioning the prompt changes shows up in git diffs cleanly, and
non-engineers can review/edit copy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.core.exceptions import InternalError

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    model: str
    temperature: float
    max_tokens: int
    system: str
    user_template: str

    def render(self, **kwargs: Any) -> str:
        """Substitute ``{placeholder}`` markers in ``user_template``."""
        try:
            return self.user_template.format(**kwargs)
        except KeyError as e:
            raise InternalError(
                error_code="PROMPT_RENDER_ERROR",
                message=f"Prompt {self.name!r} missing variable: {e!s}",
            ) from e


_cache: dict[str, PromptTemplate] = {}


def load_prompt(name: str) -> PromptTemplate:
    """Load and cache a prompt by name (no extension)."""
    if name in _cache:
        return _cache[name]

    path = _PROMPTS_DIR / f"{name}.yaml"
    if not path.is_file():
        raise InternalError(
            error_code="PROMPT_NOT_FOUND",
            message=f"Prompt template not found: {name}",
        )

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    required = {"version", "model", "temperature", "max_tokens", "system", "user_template"}
    missing = required - raw.keys()
    if missing:
        raise InternalError(
            error_code="PROMPT_INVALID",
            message=f"Prompt {name!r} missing fields: {sorted(missing)}",
        )

    tpl = PromptTemplate(
        name=name,
        version=str(raw["version"]),
        model=str(raw["model"]),
        temperature=float(raw["temperature"]),
        max_tokens=int(raw["max_tokens"]),
        system=str(raw["system"]).strip(),
        user_template=str(raw["user_template"]).strip(),
    )
    _cache[name] = tpl
    return tpl


def clear_cache() -> None:
    """Test helper — drop the cache so reloads pick up edits."""
    _cache.clear()
