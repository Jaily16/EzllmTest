"""Explicit, opt-in paid connectivity checks for configured model providers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.provider import LLMError, get_chat_model, get_embeddings, list_model_specs


PROVIDER_LABELS = {spec.provider: spec.label for spec in list_model_specs()}
SMOKE_PROMPT = "不要解释，只回复：EZLLMTEST_SMOKE_OK"
EMBEDDING_TEXT = "EzllmTest embedding smoke test"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one explicitly selected paid model connectivity check."
    )
    parser.add_argument(
        "--provider",
        choices=tuple(PROVIDER_LABELS),
        required=True,
        help="Chat provider to call",
    )
    parser.add_argument(
        "--confirm-cost",
        action="store_true",
        help="Confirm that this command may make a billable external API request",
    )
    parser.add_argument(
        "--with-embedding",
        action="store_true",
        help="Also call Zhipu embedding-3; valid only with --provider zhipu",
    )
    return parser.parse_args(argv)


def _safe_content(result: object) -> str:
    content = getattr(result, "content", "")
    if not isinstance(content, str) or not content.strip():
        raise SystemExit("Chat smoke test returned an empty response.")
    return " ".join(content.strip().split())[:200]


def _print_usage(result: object) -> None:
    usage = getattr(result, "usage_metadata", None)
    if not isinstance(usage, dict):
        return
    fields = []
    for name in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(name)
        if isinstance(value, int):
            fields.append(f"{name}={value}")
    if fields:
        print("Chat usage: " + ", ".join(fields))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.confirm_cost:
        raise SystemExit(
            "Paid API call not confirmed. Re-run with --confirm-cost after checking "
            "the selected provider key, balance, and model settings."
        )
    if args.with_embedding and args.provider != "zhipu":
        raise SystemExit("--with-embedding is only supported with --provider zhipu.")

    label = PROVIDER_LABELS[args.provider]
    try:
        answer = get_chat_model(label).invoke(SMOKE_PROMPT)
    except LLMError as exc:
        raise SystemExit(f"Chat smoke test failed: {exc}") from None
    except Exception:
        raise SystemExit(
            "Chat smoke test failed with an unexpected provider error; details redacted."
        ) from None

    print(f"Provider: {args.provider}")
    print(f"Public label: {label}")
    print(f"Chat response: {_safe_content(answer)}")
    _print_usage(answer)

    if args.with_embedding:
        try:
            vector = get_embeddings().embed_query(EMBEDDING_TEXT)
        except Exception:
            raise SystemExit(
                "Embedding smoke test failed with an unexpected provider error; "
                "details redacted."
            ) from None
        if not vector:
            raise SystemExit("Embedding smoke test returned an empty vector.")
        print(f"Embedding dimensions: {len(vector)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
