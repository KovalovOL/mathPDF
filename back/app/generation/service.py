import logging

from time import perf_counter


from app.generation.models import (
    ContentValidationError,
    GenerateRequest,
    GeneratedContent,
    GenerationError,
    InputDocument,
    Progress,
    StudyProvider,
)

logger = logging.getLogger(__name__)

from app.study.policies import validate_item, question_fingerprint


def _validate_questions(result, request, source):
    seen = set()
    try:
        for index, item in enumerate(result.content.items, 1):
            item.goal_step = index
            validate_item(item, request.mode, source.document.id, source.pages)
            fingerprint = question_fingerprint(item)
            if fingerprint in seen:
                raise ContentValidationError(
                    "duplicate_question", "The model returned a repeated question."
                )
            seen.add(fingerprint)
    except ContentValidationError as error:
        logger.warning(
            "Study response rejected code=%s requested=%s", error.code, request.count
        )
        raise GenerationError(
            str(error) + " No partial set was created. Please try again."
        ) from None


def _require_complete_set(result, request):
    if result.insufficient_source:
        raise GenerationError(
            f"The selected pages could not support {request.count} distinct items. Choose more source pages or request fewer items."
        )
    if len(result.content.items) != request.count:
        logger.warning(
            "Study response rejected code=wrong_count requested=%s received=%s",
            request.count,
            len(result.content.items),
        )
        raise GenerationError(
            f"The model returned {len(result.content.items)} of {request.count} requested items. No partial set was created. Please try again."
        )


class GenerationService:
    def __init__(self, prompts):
        self._prompts = prompts

    async def collect(
        self,
        documents: list[InputDocument],
        request: GenerateRequest,
        provider: StudyProvider,
        progress: Progress,
    ) -> tuple[GeneratedContent, dict]:
        source = documents[0]
        system, task, hashes = self._prompts.load(request, documents)
        started = perf_counter()
        progress({"phase": "generating", "accepted_count": 0, "attempt": 1})
        logger.info(
            "Study single request started requested=%s mode=%s",
            request.count,
            request.mode,
        )
        result = await provider.generate(
            documents, system, task, count=request.count, mode=request.mode
        )
        _require_complete_set(result, request)
        progress({"phase": "checking"})
        _validate_questions(result, request, source)
        progress({"accepted_count": request.count})
        elapsed = round((perf_counter() - started) * 1000)
        logger.info(
            "Study single request completed requested=%s accepted=%s duration_ms=%s",
            request.count,
            request.count,
            elapsed,
        )
        return (
            result.content,
            {
                "provider": result.provider,
                "model": result.model,
                "prompt_hashes": hashes,
                "math_check": "on_display",
                "formatting_policy": "best_effort",
                "requested_count": request.count,
                "generation_attempts": 1,
                "provider_requests": 1,
                "generation_strategy": "single_request",
                "generation_duration_ms": elapsed,
            },
        )
