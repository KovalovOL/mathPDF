"""OpenAI HTTP transport; exactly one provider request per generation."""

from asyncio import to_thread
import base64
import logging
from time import perf_counter
from typing import Literal
from openai import APIError, AsyncOpenAI, pydantic_function_tool
from pydantic import ValidationError
from app.study.contract import GeneratedContent
from app.generation.models import GenerationError, InputDocument, ProviderResult
from app.generation.output import InsufficientSource, set_response_format
from app.usage.context import usage_context


class OpenAIProvider:

    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        documents: list[InputDocument],
        system: str,
        task: str,
        *,
        count: int,
        mode: Literal["flashcards", "problems"],
    ) -> ProviderResult:
        content = self._input_content(documents, task)
        output_cap = min(30000, 1000 + (650 if mode == "flashcards" else 1000) * count)
        estimated_tokens = (
            output_cap
            + sum(
                (
                    (
                        len(d.pages) * 4000
                        if d.pages is not None
                        else (
                            d.document.page_count * 4000
                            if d.document.page_count
                            else (len(d.data) + 2) // 3
                        )
                    )
                    for d in documents
                )
            )
            + (len(system.encode()) + len(task.encode()) + 2) // 3
        )
        response_format = set_response_format(count, mode)
        function = pydantic_function_tool(response_format)["function"]
        logger = logging.getLogger(__name__)
        started = perf_counter()
        tracking = usage_context.get()
        attempt = await self._start_attempt(
            tracking, documents, estimated_tokens, system, task
        )
        logger.info("Provider request started phase=generating requested=%s", count)
        response = await self._send_request(
            function, output_cap, content, system, started, tracking, attempt, logger
        )
        await self._observe_response(response, attempt, tracking, started, logger)
        return self._decode_response(response, documents, count, mode, logger)

    def _decode_response(self, response, documents, count, mode, logger):
        try:
            result = (
                set_response_format(count, mode, permissive=True)
                .model_validate_json(response.output_text)
                .result
            )
            if isinstance(result, InsufficientSource):
                return ProviderResult(
                    content=GeneratedContent(items=[], notes=[]),
                    provider="openai",
                    model=self._model,
                    insufficient_source=True,
                )
            items = [
                item.expand(documents[0].document.id, index, mode)
                for index, item in enumerate(result.items, 1)
            ]
        except ValidationError as error:
            fields = [
                {"type": entry["type"], "loc": entry["loc"]} for entry in error.errors()
            ]
            logger.warning("Study response invalid_fields=%s", fields)
            raise GenerationError(
                "The model returned an invalid study set. No partial set was created. Please try again."
            ) from None
        return ProviderResult(
            content=GeneratedContent(items=items, notes=[]),
            provider="openai",
            model=self._model,
        )

    async def _observe_response(self, response, attempt, tracking, started, logger):
        if attempt:
            await to_thread(
                tracking["store"].finish,
                attempt,
                "received",
                getattr(response, "usage", None),
                round((perf_counter() - started) * 1000),
                getattr(response, "_request_id", None),
            )
            await to_thread(
                tracking["store"].response,
                attempt,
                getattr(response, "model", None) or self._model,
                response.status,
                response.output_text,
            )
        logger.info(
            "Provider request finished phase=generating status=%s output_tokens=%s duration_ms=%s",
            response.status,
            getattr(response.usage, "output_tokens", None),
            round((perf_counter() - started) * 1000),
        )
        if any(
            (
                part.type == "refusal"
                for output in response.output
                if output.type == "message"
                for part in output.content
            )
        ):
            raise GenerationError(
                "The generation service could not create material from these pages. Try different source pages."
            )
        if response.status != "completed":
            logger.warning(
                "Study response incomplete reason=%s output_tokens=%s",
                getattr(response.incomplete_details, "reason", None),
                getattr(response.usage, "output_tokens", None),
            )
            raise GenerationError(
                "The model did not complete the requested set. No partial set was created. Please try again."
            )

    async def _provider_failure(self, error, attempt, tracking, started, logger):
        if attempt:
            await to_thread(
                tracking["store"].finish,
                attempt,
                "provider_error",
                None,
                round((perf_counter() - started) * 1000),
                getattr(error, "request_id", None),
                unbilled=getattr(error, "status_code", None)
                in {400, 401, 403, 404, 409, 413, 422, 429},
            )
        status = getattr(error, "status_code", None)
        logger.warning(
            "Provider request failed status=%s error_type=%s duration_ms=%s",
            status,
            type(error).__name__,
            round((perf_counter() - started) * 1000),
        )
        messages = {
            401: "Generation is unavailable because of a server configuration problem.",
            429: "The generation service has reached its usage limit. Please try again later.",
            400: "The generation service could not process these files. Try fewer pages or different files.",
        }
        raise GenerationError(
            messages.get(
                status,
                "The generation service is unavailable or timed out. Try again later.",
            )
        ) from None

    async def _send_request(
        self, function, output_cap, content, system, started, tracking, attempt, logger
    ):
        try:
            async with AsyncOpenAI(
                api_key=self._api_key, timeout=120, max_retries=0
            ) as client:
                response = await client.responses.create(
                    model=self._model,
                    instructions=system,
                    input=[{"role": "user", "content": content}],
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": function["name"],
                            "strict": True,
                            "schema": function["parameters"],
                        }
                    },
                    max_output_tokens=output_cap,
                    store=False,
                )
        except APIError as error:
            await self._provider_failure(error, attempt, tracking, started, logger)
        return response

    async def _start_attempt(self, tracking, documents, estimated_tokens, system, task):
        attempt = None
        if tracking and tracking["store"]:
            attempt = await to_thread(
                tracking["store"].start,
                tracking["user_id"],
                "openai",
                self._model,
                {
                    "estimated_tokens": estimated_tokens,
                    "selection": tracking["request"],
                    "system_prompt": system,
                    "task_prompt": task,
                    "documents": [
                        {
                            "id": d.document.id,
                            "filename": d.document.filename,
                            "sha256": d.document.sha256,
                            "pages": d.pages,
                            "role": d.role,
                        }
                        for d in documents
                    ],
                },
            )
            tracking["attempt_id"] = attempt
        return attempt

    def _input_content(self, documents, task):
        content = []
        for entry in documents:
            content.append({"type": "input_text", "text": entry.label})
            data_url = (
                f"data:{entry.document.media_type};base64,"
                + base64.b64encode(entry.data).decode()
            )
            if entry.document.media_type.startswith("image/"):
                content.append(
                    {"type": "input_image", "image_url": data_url, "detail": "auto"}
                )
            else:
                content.append(
                    {
                        "type": "input_file",
                        "filename": entry.filename,
                        "file_data": data_url,
                    }
                )
        content.append({"type": "input_text", "text": task})
        return content
