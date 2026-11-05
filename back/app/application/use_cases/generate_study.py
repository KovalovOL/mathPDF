import logging
from asyncio import timeout, to_thread
from datetime import datetime, timezone
from app.study.contract import ContextSnapshot, StudySet
from app.generation.models import (
    GENERATION_SECONDS,
    GenerateRequest,
    GenerationError,
    Progress,
    StudyProvider,
)
from app.usage.context import usage_context

logger = logging.getLogger(__name__)


class GenerateStudy:
    def __init__(self, preparation, collector, usage):
        self._preparation = preparation
        self._collector = collector
        self._usage = usage

    async def execute(
        self,
        owner_id: str,
        request: GenerateRequest,
        provider: StudyProvider,
        progress: Progress | None = None,
    ) -> StudySet:
        if self._usage:
            await to_thread(self._usage.quota.check, owner_id)
        tracking = {
            "store": self._usage,
            "user_id": owner_id,
            "request": request.model_dump(mode="json"),
            "attempt_id": None,
        }
        context_token = usage_context.set(tracking)
        progress = progress or (lambda _: None)
        documents, content, metadata = await self._collect_with_deadline(
            owner_id, request, provider, progress, tracking, context_token
        )
        if tracking["store"] and tracking["attempt_id"]:
            await to_thread(
                tracking["store"].outcome, tracking["attempt_id"], "completed"
            )
        return self._make_set(documents, request, content, metadata)

    def _make_set(self, documents, request, content, metadata):
        source = documents[0]
        label = "Flashcards" if request.mode == "flashcards" else "Problems"
        selection = (
            str(source.pages[0])
            if len(source.pages) == 1
            else f"{source.pages[0]}–{source.pages[-1]}"
        )
        return StudySet(
            title=f"{label} · {source.document.filename} · {selection}",
            document=source.document,
            pages=source.pages,
            mode=request.mode,
            comment=request.comment.strip(),
            difficulty=request.difficulty,
            context_documents=[
                ContextSnapshot(document=entry.document, pages=entry.pages)
                for entry in documents[1:]
            ],
            **content.model_dump(),
            metadata={
                **metadata,
                "source_check": "unchecked",
                "line_references": "page-only",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def _collect_with_deadline(
        self, owner_id, request, provider, progress, tracking, context_token
    ):
        try:
            async with timeout(GENERATION_SECONDS):
                progress({"phase": "preparing", "accepted_count": 0})
                documents = await to_thread(
                    self._preparation.prepare, request, owner_id
                )
                content, metadata = await self._collector.collect(
                    documents, request, provider, progress
                )
        except BaseException as error:
            if tracking["store"] and tracking["attempt_id"]:
                try:
                    await to_thread(
                        tracking["store"].outcome,
                        tracking["attempt_id"],
                        (
                            "cancelled"
                            if type(error).__name__ == "CancelledError"
                            else "failed"
                        ),
                    )
                except Exception:
                    logger.warning(
                        "Could not update the failed provider attempt status id=%s",
                        tracking["attempt_id"],
                    )
            if isinstance(error, TimeoutError):
                raise GenerationError(
                    f"Generation timed out before all {request.count} items were ready. Try again with fewer items or fewer source pages."
                ) from None
            raise
        finally:
            usage_context.reset(context_token)
        return documents, content, metadata
