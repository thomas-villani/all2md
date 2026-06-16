"""Shared Claude (Anthropic) client helper for the all2md LLM examples.

The LLM examples in this folder all talk to the same place through this module,
so there is exactly one copy of the SDK wiring to keep current. Two providers
are available:

- ``anthropic`` -- the real thing, via the official ``anthropic`` SDK. Requires
  ``pip install anthropic`` and an ``ANTHROPIC_API_KEY`` environment variable.
- ``mock`` -- a deterministic, offline stand-in so every example runs end-to-end
  in CI or on a laptop with no API key (it echoes a tagged slice of the prompt).

Each provider returns a *client callable* with the signature
``client(prompt: str, system: str | None = None) -> str``.

Example
-------
    from _llm_client import get_client

    ask = get_client("anthropic")          # or "mock"
    answer = ask("Summarise this:\\n" + text, system="You are concise.")
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable, Optional

# Default to the most capable Opus model. For high-volume or cost-sensitive work
# -- e.g. translating *every* text node of a long document -- switch to a cheaper
# current model such as "claude-haiku-4-5" or "claude-sonnet-4-6".
DEFAULT_MODEL = "claude-opus-4-8"

# A client callable: (user_prompt, optional system_prompt) -> completion text.
LLMClient = Callable[..., str]


def anthropic_client(model: str = DEFAULT_MODEL, max_tokens: int = 4096) -> LLMClient:
    """Build a Claude-backed client callable using the official ``anthropic`` SDK.

    Parameters
    ----------
    model : str
        Claude model id. Defaults to :data:`DEFAULT_MODEL`.
    max_tokens : int
        Maximum tokens to generate per call.

    Returns
    -------
    LLMClient
        A callable ``(prompt, system=None) -> str``.
    """
    import anthropic  # imported lazily so `mock` works without the SDK installed

    # Reads ANTHROPIC_API_KEY from the environment.
    client = anthropic.Anthropic()

    def complete(prompt: str, system: Optional[str] = None) -> str:
        # Note: Opus/Fable models reject temperature/top_p and `budget_tokens`;
        # we deliberately pass neither. `system` is omitted when not provided.
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = client.messages.create(**kwargs)
        return "".join(block.text for block in response.content if block.type == "text")

    return complete


def mock_client(model: str = DEFAULT_MODEL, max_tokens: int = 4096) -> LLMClient:
    """Build an offline stand-in that needs no API key.

    Useful for trying an example end-to-end without spending tokens. It does not
    call a model -- it returns a short, tagged echo of the prompt.
    """

    def complete(prompt: str, system: Optional[str] = None) -> str:
        return f"[mock:{model}] {prompt.strip()[:280]}"

    return complete


@lru_cache(maxsize=8)
def get_client(provider: str = "anthropic", *, model: str = DEFAULT_MODEL, max_tokens: int = 4096) -> LLMClient:
    """Return a client callable for ``provider`` ("anthropic" or "mock").

    The result is cached so repeated calls reuse one underlying SDK client.
    """
    if provider == "mock":
        return mock_client(model=model, max_tokens=max_tokens)
    if provider == "anthropic":
        return anthropic_client(model=model, max_tokens=max_tokens)
    raise ValueError(f"Unknown provider {provider!r} (expected 'anthropic' or 'mock')")
