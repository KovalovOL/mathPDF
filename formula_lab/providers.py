"""OpenAI adapter. Provider-specific request details stay out of use cases."""

import base64
import logging

from openai import APIError, AsyncOpenAI, LengthFinishReasonError
from pydantic import ValidationError

from .study import GeneratedContent, GenerationError, InputDocument, ProviderResult


class OpenAIProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate(self, documents: list[InputDocument], system: str, task: str) -> ProviderResult:
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
                    text_format=GeneratedContent,
                    max_output_tokens=8000,
                    store=False,
                )
        except APIError as error:
            # SDK errors can include request/response details; never forward them.
            status = getattr(error, "status_code", None)
            messages = {
                401: "OpenAI rejected the API credentials. Check the server configuration.",
                429: "OpenAI rate or quota limit reached. Check your account and try later.",
                400: "OpenAI rejected the request. Check that OPENAI_MODEL supports PDF input and structured output.",
            }
            raise GenerationError(messages.get(status, "OpenAI is unavailable or timed out. Try again later.")) from None
        except ValidationError as error:
            logging.getLogger(__name__).warning("Study response validation: %s", error.errors(
                include_input=False, include_context=False, include_url=False))
            raise GenerationError("OpenAI returned invalid study content. Try generating again.") from None
        except (LengthFinishReasonError, ValueError) as error:
            logging.getLogger(__name__).warning("Study response parse failed: %s", type(error).__name__)
            raise GenerationError("OpenAI returned incomplete or invalid study content. Try fewer items.") from None
        if response.status != "completed" or response.output_parsed is None:
            raise GenerationError("OpenAI did not return a complete study set. Try fewer items or different pages.")
        return ProviderResult(content=response.output_parsed, provider="openai", model=self.model)
