"""OpenAI adapter. Provider-specific request details stay out of use cases."""

import base64
import logging
from functools import lru_cache
from typing import Literal

from openai import APIError, AsyncOpenAI, LengthFinishReasonError
from pydantic import Field, ValidationError

from .study import (BATCH_SIZE, GeneratedContent, GenerationError, InputDocument, ProviderResult,
                    RetryableGenerationError, StrictModel, StudyItem)


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


class OpenAIProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate(self, documents: list[InputDocument], system: str, task: str,
                       *, count: int) -> ProviderResult:
        content = []
        for entry in documents:
            content.append({"type": "input_text", "text": entry.label})
            data_url = f"data:{entry.document.media_type};base64," + base64.b64encode(entry.data).decode()
            if entry.document.media_type.startswith("image/"):
                content.append({"type": "input_image", "image_url": data_url, "detail": "auto"})
            else:
                content.append({"type": "input_file", "filename": entry.filename, "file_data": data_url})
        content.append({"type": "input_text", "text": task})
        try:
            async with AsyncOpenAI(api_key=self.api_key, timeout=120, max_retries=0) as client:
                response = await client.responses.parse(
                    model=self.model,
                    instructions=system,
                    input=[{"role": "user", "content": content}],
                    text_format=batch_response_format(count),
                    max_output_tokens=12000,
                    store=False,
                )
        except APIError as error:
            # SDK errors can include request/response details; never forward them.
            status = getattr(error, "status_code", None)
            messages = {
                401: "Generation is unavailable because of a server configuration problem.",
                429: "The generation service has reached its usage limit. Please try again later.",
                400: "The generation service could not process these files. Try fewer pages or different files.",
            }
            raise GenerationError(messages.get(status, "The generation service is unavailable or timed out. Try again later.")) from None
        except ValidationError as error:
            logging.getLogger(__name__).warning("Study response validation: %s", error.errors(
                include_input=False, include_context=False, include_url=False))
            raise RetryableGenerationError("invalid_response", "The study content needs to be regenerated.") from None
        except (LengthFinishReasonError, ValueError) as error:
            logging.getLogger(__name__).warning("Study response parse failed: %s", type(error).__name__)
            raise RetryableGenerationError("incomplete_response", "The study response was incomplete.") from None
        if any(part.type == "refusal" for output in response.output if output.type == "message"
               for part in output.content):
            raise GenerationError("The generation service could not create material from these pages. "
                                  "Try different source pages.")
        if response.status != "completed" or response.output_parsed is None:
            raise RetryableGenerationError("incomplete_response", "The study response was incomplete.")
        result = response.output_parsed.result
        insufficient = isinstance(result, InsufficientSource)
        content = GeneratedContent(items=[], notes=[result.reason]) if insufficient else GeneratedContent(
            items=result.items, notes=result.notes)
        return ProviderResult(content=content, provider="openai", model=self.model,
                              insufficient_source=insufficient)
