"""OpenAI adapter. Provider-specific request details stay out of use cases."""

import base64
import logging
from functools import lru_cache
from time import perf_counter
from typing import Literal

from openai import APIError, AsyncOpenAI, pydantic_function_tool
from pydantic import Field, ValidationError

from .study import (BATCH_SIZE, MAX_ITEMS, GeneratedContent, GenerationError, InputDocument, LearningGoal,
                    PlanResult, ProviderResult, RetryableGenerationError, StrictModel, StudyItem)


class InsufficientSource(StrictModel):
    status: Literal["insufficient_source"]
    reason: str = Field(min_length=1, max_length=2000)


@lru_cache(maxsize=BATCH_SIZE)
def batch_response_format(count: int) -> type[StrictModel]:
    if not 1 <= count <= BATCH_SIZE:
        raise ValueError("Invalid generation batch size.")

    class CompletedBatch(StrictModel):
        status: Literal["completed"]
        items: list[StudyItem] = Field(min_length=count, max_length=count)
        notes: list[str] = Field(max_length=10)

    class BatchResponse(StrictModel):
        result: CompletedBatch | InsufficientSource

    return BatchResponse


@lru_cache(maxsize=MAX_ITEMS)
def plan_response_format(count: int) -> type[StrictModel]:
    if not 1 <= count <= MAX_ITEMS:
        raise ValueError("Invalid learning plan size.")

    class CompletedPlan(StrictModel):
        status: Literal["completed"]
        goals: list[LearningGoal] = Field(min_length=count, max_length=count)

    class PlanResponse(StrictModel):
        result: CompletedPlan | InsufficientSource

    return PlanResponse


class OpenAIProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def _request(self, documents: list[InputDocument], system: str, task: str,
                       response_format: type[StrictModel], *, phase: str) -> StrictModel:
        content = []
        for entry in documents:
            content.append({"type": "input_text", "text": entry.label})
            data_url = f"data:{entry.document.media_type};base64," + base64.b64encode(entry.data).decode()
            if entry.document.media_type.startswith("image/"):
                content.append({"type": "input_image", "image_url": data_url, "detail": "auto"})
            else:
                content.append({"type": "input_file", "filename": entry.filename, "file_data": data_url})
        content.append({"type": "input_text", "text": task})
        # Use the SDK's public strict-schema converter, then inspect completion
        # status BEFORE parsing. responses.parse attempts to parse truncated JSON.
        function = pydantic_function_tool(response_format)["function"]
        logger = logging.getLogger(__name__)
        started = perf_counter()
        logger.info("Provider request started phase=%s", phase)
        try:
            async with AsyncOpenAI(api_key=self.api_key, timeout=120, max_retries=0) as client:
                response = await client.responses.create(
                    model=self.model,
                    instructions=system,
                    input=[{"role": "user", "content": content}],
                    text={"format": {"type": "json_schema", "name": function["name"],
                                     "strict": True, "schema": function["parameters"]}},
                    max_output_tokens=12000,
                    store=False,
                )
        except APIError as error:
            # SDK errors can include request/response details; never forward them.
            status = getattr(error, "status_code", None)
            logger.warning("Provider request failed phase=%s status=%s error_type=%s duration_ms=%s",
                           phase, status, type(error).__name__, round((perf_counter() - started) * 1000))
            messages = {
                401: "Generation is unavailable because of a server configuration problem.",
                429: "The generation service has reached its usage limit. Please try again later.",
                400: "The generation service could not process these files. Try fewer pages or different files.",
            }
            raise GenerationError(messages.get(status, "The generation service is unavailable or timed out. Try again later.")) from None
        logger.info("Provider request finished phase=%s status=%s output_tokens=%s duration_ms=%s",
                    phase, response.status, getattr(response.usage, "output_tokens", None), round((perf_counter() - started) * 1000))
        if any(part.type == "refusal" for output in response.output if output.type == "message"
               for part in output.content):
            raise GenerationError("The generation service could not create material from these pages. "
                                  "Try different source pages.")
        if response.status != "completed":
            reason = getattr(response.incomplete_details, "reason", None)
            logging.getLogger(__name__).warning("Study provider phase=%s status=%s reason=%s output_tokens=%s",
                phase, response.status, reason, getattr(response.usage, "output_tokens", None))
            if reason == "content_filter":
                raise GenerationError("The generation service could not complete this material. Try different source pages.")
            code = "output_limit" if reason == "max_output_tokens" else "incomplete_response"
            raise RetryableGenerationError(code, "The study response was incomplete.")
        try:
            return response_format.model_validate_json(response.output_text).result
        except ValidationError as error:
            # Do not log model content, quotes, prompts or error messages containing input.
            fields = [{"type": entry["type"], "loc": entry["loc"]} for entry in error.errors()]
            logging.getLogger(__name__).warning("Study provider phase=%s invalid_fields=%s", phase, fields)
            raise RetryableGenerationError("invalid_response", "The study content needs to be regenerated.") from None

    async def plan(self, documents: list[InputDocument], system: str, task: str,
                   *, count: int) -> PlanResult:
        result = await self._request(documents, system, task, plan_response_format(count), phase="planning")
        insufficient = isinstance(result, InsufficientSource)
        return PlanResult(goals=[] if insufficient else result.goals, provider="openai", model=self.model,
                          insufficient_source=insufficient)

    async def generate(self, documents: list[InputDocument], system: str, task: str,
                       *, count: int) -> ProviderResult:
        result = await self._request(documents, system, task, batch_response_format(count), phase="generating")
        insufficient = isinstance(result, InsufficientSource)
        content = GeneratedContent(items=[], notes=[result.reason]) if insufficient else GeneratedContent(
            items=result.items, notes=result.notes)
        return ProviderResult(content=content, provider="openai", model=self.model,
                              insufficient_source=insufficient)
