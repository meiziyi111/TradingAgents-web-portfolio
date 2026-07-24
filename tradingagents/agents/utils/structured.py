"""Shared helpers for invoking an agent with structured output and a graceful fallback.

The Portfolio Manager, Trader, and Research Manager all follow the same
canonical pattern:

1. At agent creation, wrap the LLM with ``with_structured_output(Schema)``
   so the model returns a typed Pydantic instance. If the provider does
   not support structured output (rare; mostly older Ollama models), the
   wrap is skipped and the agent uses free-text generation instead.
2. At invocation, run the structured call and render the result back to
   markdown. If the structured call itself fails for any reason
   (malformed JSON from a weak model, transient provider issue), fall
   back to a plain ``llm.invoke`` so the pipeline never blocks.

Centralising the pattern here keeps the agent factories small and ensures
all three agents log the same warnings when fallback fires.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _structured_retry_prompt(prompt: Any) -> Any:
    """Add a provider-agnostic correction instruction for a second typed attempt."""
    instruction = (
        "Your previous response did not satisfy the required schema. Retry now. "
        "Return valid JSON with every required field exactly as named by the schema; "
        "do not substitute action for rating, and do not omit any field."
    )
    if isinstance(prompt, str):
        return f"{prompt}\n\n{instruction}"
    if isinstance(prompt, list):
        return [*prompt, {"role": "user", "content": instruction}]
    return prompt


def bind_structured(llm: Any, schema: type[T], agent_name: str) -> Optional[Any]:
    """Return ``llm.with_structured_output(schema)`` or ``None`` if unsupported.

    Logs a warning when the binding fails so the user understands the agent
    will use free-text generation for every call instead of one-shot fallback.
    """
    try:
        # DeepSeek thinking models expose reliable JSON mode but may return an
        # empty tool result on long prompts. Prefer JSON mode for them so the
        # Pydantic contract is actually materialized.
        model_name = getattr(llm, "model_name", "")
        method = "json_mode" if isinstance(model_name, str) and model_name.lower().startswith("deepseek") else None
        if method:
            return llm.with_structured_output(schema, method=method)
        return llm.with_structured_output(schema)
    except (NotImplementedError, AttributeError) as exc:
        logger.warning(
            "%s: provider does not support with_structured_output (%s); "
            "falling back to free-text generation",
            agent_name, exc,
        )
        return None


def invoke_structured_or_freetext(
    structured_llm: Optional[Any],
    plain_llm: Any,
    prompt: Any,
    render: Callable[[T], str],
    agent_name: str,
    allow_fallback: bool = True,
) -> str:
    """Run the structured call and render to markdown; fall back to free-text on any failure.

    ``prompt`` is whatever the underlying LLM accepts (a string for chat
    invocations, a list of message dicts for chat models that take that
    shape). The same value is forwarded to the free-text path so the
    fallback sees the same input the structured call did.
    """
    if not allow_fallback and structured_llm is None:
        raise RuntimeError(
            f"{agent_name} requires structured output, but the configured provider does not support it."
        )

    if structured_llm is not None:
        try:
            result = structured_llm.invoke(prompt)
            if result is None:
                raise ValueError("structured-output provider returned an empty result")
            return render(result)
        except Exception as exc:
            if not allow_fallback:
                logger.warning(
                    "%s: structured output failed validation; retrying once with explicit field correction (%s)",
                    agent_name, exc,
                )
                try:
                    result = structured_llm.invoke(_structured_retry_prompt(prompt))
                    if result is None:
                        raise ValueError("structured-output retry returned an empty result")
                    return render(result)
                except Exception as retry_exc:
                    raise RuntimeError(
                        f"{agent_name} structured output failed after one schema retry; "
                        f"no incomplete decision was saved: {retry_exc}"
                    ) from retry_exc
            logger.warning(
                "%s: structured-output invocation failed (%s); retrying once as free text",
                agent_name, exc,
            )

    response = plain_llm.invoke(prompt)
    return response.content
