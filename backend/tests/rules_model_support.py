"""Liste von OpenRouter (GET /models) für die Tests der Modellwahl (PLAN_AN2_PLU 8), ohne Netz."""

from typing import Any


def model(
    model_id: str,
    prompt: str = "0.000004",
    completion: str = "0.00002",
    *,
    modalities: tuple[str, ...] = ("text", "image", "file"),
    parameters: tuple[str, ...] = ("tools", "tool_choice", "reasoning"),
    **pricing: str,
) -> dict[str, Any]:
    return {
        "id": model_id,
        "name": model_id.split("/")[-1].replace("-", " ").title(),
        "context_length": 1_000_000,
        "architecture": {"input_modalities": list(modalities)},
        "supported_parameters": list(parameters),
        "pricing": {"prompt": prompt, "completion": completion, **pricing},
    }


LISTING = {
    "data": [
        model("anthropic/claude-opus-5.5", input_cache_read="0.0000004", input_cache_write="0.000005"),
        model("anthropic/claude-sonnet-5", "0.000002", "0.00001"),
        model("anthropic/claude-opus-5.5:batch", "0.000002", "0.00001"),
        model("~anthropic/claude-opus-latest"),
        model("openai/text-only", modalities=("text",)),
        model("google/no-forced-tool", parameters=("tools",)),
        model("openrouter/auto", "-1", "-1"),
        model("vendor/" + "x" * 60),
        "kein Eintrag",
    ]
}
