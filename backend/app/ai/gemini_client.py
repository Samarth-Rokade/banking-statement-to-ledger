import json
import time
from pathlib import Path
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config.settings import get_settings

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

ModelT = TypeVar("ModelT", bound=BaseModel)


class GeminiCallError(Exception):
    """Raised when Gemini fails to return valid, schema-conforming JSON after one retry."""


class GeminiClient:
    """Thin, prompt-agnostic wrapper: render a template, call the model, validate the
    JSON array response against a given Pydantic model. Business logic (batching,
    guardrails, what to do on failure) lives in the caller (e.g. LedgerPredictor),
    not here - this class only knows how to talk to Gemini and enforce structure.
    """

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self._client = genai.Client(api_key=api_key or settings.gemini_api_key)

    def call(
        self,
        prompt_name: str,
        context: dict[str, str],
        model: str,
        response_model: type[ModelT],
    ) -> tuple[list[ModelT], str, int]:
        """Returns (parsed_items, raw_response_text, latency_ms). Retries once, with
        the validation error fed back into the prompt, before raising GeminiCallError.
        """
        prompt = self._render(prompt_name, context)

        last_error: Exception | None = None
        for _attempt in range(2):
            raw_text, latency_ms = self._generate(prompt, model)
            try:
                payload = json.loads(raw_text)
                items = [response_model.model_validate(item) for item in payload]
                return items, raw_text, latency_ms
            except (json.JSONDecodeError, ValidationError, TypeError) as exc:
                last_error = exc
                prompt = (
                    f"{prompt}\n\n---\nYour previous response failed validation with "
                    f"this error: {exc}\nRespond again with corrected JSON only, no "
                    f"markdown fences, matching the exact schema above."
                )
        raise GeminiCallError(f"Gemini response failed validation after retry: {last_error}")

    def _render(self, prompt_name: str, context: dict[str, str]) -> str:
        template = (PROMPTS_DIR / f"{prompt_name}.md").read_text(encoding="utf-8")
        for key, value in context.items():
            template = template.replace(f"{{{{{key}}}}}", value)
        return template

    def _generate(self, prompt: str, model: str) -> tuple[str, int]:
        start = time.monotonic()
        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"),
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        return response.text or "", latency_ms
