"""Local PDF study workflow with optional source-layout inspection."""

import argparse
import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from .extract import PdfSource
from .models import Review
from .store import FormulaStore
from .variants import replace_sign
from .providers import OpenAIProvider
from .study import GenerateRequest, GenerationError, StudyProvider, StudySet, generate_study, validate_study
from .workspace import MAX_UPLOAD_BYTES, Workspace
from .pdf_export import ExportError, export_pdf


class Selection(BaseModel):
    page: int
    bbox: tuple[float, float, float, float]
    title: str = Field(default="Source formula", max_length=180)


class SignChange(BaseModel):
    node_id: str = Field(max_length=100)
    replacement: str = Field(max_length=2)


def create_app(pdf_path: Path, data_dir: Path, provider: StudyProvider | None = None) -> FastAPI:
    load_dotenv(Path.cwd() / ".env", override=False)
    source = PdfSource(pdf_path, data_dir)
    store = FormulaStore(data_dir, source.sha256)
    workspace = Workspace(data_dir)
    default_document = workspace.add_document(source.path.name, source.path.read_bytes())
    app = FastAPI(title="mathPDF", docs_url="/api/docs", redoc_url=None)
    app.state.source, app.state.store = source, store
    app.state.workspace = workspace
    static = Path(__file__).parent / "static"
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY", "")
    app.state.provider = provider or (OpenAIProvider(key, model) if key else None)
    generation_lock = asyncio.Lock()
    export_lock = asyncio.Lock()

    @app.exception_handler(ExportError)
    @app.exception_handler(GenerationError)
    async def generation_failed(request, error):
        return Response(json.dumps({"detail": str(error)}), status_code=502,
                        media_type="application/json")

    @app.exception_handler(ValueError)
    async def invalid_request(request, error):
        return Response(json.dumps({"detail":str(error)}),status_code=400,media_type="application/json")

    @app.exception_handler(KeyError)
    async def missing_record(request, error):
        return Response(json.dumps({"detail":str(error.args[0]) if error.args else "Resource not found"}),status_code=404,media_type="application/json")

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    @app.get("/api/document")
    def document():
        return {"filename":source.path.name,"sha256":source.sha256,"page_count":source.page_count}

    @app.get("/api/generation/config")
    def generation_config():
        return {"configured": app.state.provider is not None, "max_pages": 100, "max_items": 10,
                "max_context_files": 6, "max_upload_mb": 25, "default_document_id": default_document.id}

    @app.get("/api/documents")
    def documents():
        return workspace.documents()

    @app.post("/api/documents", status_code=201)
    async def upload_document(file: UploadFile):
        try:
            data = await file.read(MAX_UPLOAD_BYTES + 1)
            return await run_in_threadpool(workspace.add_document, file.filename or "document", data)
        finally:
            await file.close()

    @app.get("/api/documents/{identifier}/file")
    def workspace_file(identifier: str, download: bool = False):
        record = workspace.document(identifier)
        return FileResponse(workspace.path(identifier), media_type=record.media_type,
                            filename=record.filename,
                            content_disposition_type="attachment" if download else "inline")

    @app.get("/api/study-sets")
    def study_sets():
        return workspace.sets()

    @app.get("/api/study-sets/{identifier}")
    def study_set(identifier: str):
        return StudySet.model_validate(workspace.study_set(identifier))

    def validate_result(result: StudySet):
        result.document = workspace.document(result.document.id)
        if not result.document.page_count or any(p < 1 or p > result.document.page_count for p in result.pages):
            raise ValueError("The study set contains invalid source pages.")
        if len(set(result.pages)) != len(result.pages):
            raise ValueError("The study set repeats a source page.")
        for entry in result.context_documents:
            entry.document = workspace.document(entry.document.id)
            if entry.pages is not None and (not entry.document.page_count or any(
                    p < 1 or p > entry.document.page_count for p in entry.pages)):
                raise ValueError("The study set contains invalid context pages.")
        validate_study(result, result.mode, result.document.id, result.pages)
        if not result.items:
            raise ValueError("There are no study items to save or export.")

    @app.post("/api/study-sets")
    def save_study_set(result: StudySet):
        validate_result(result)
        return workspace.save_set(result.model_dump(mode="json"))

    @app.post("/api/study/export.pdf")
    async def download_study_pdf(result: StudySet):
        validate_result(result)
        if export_lock.locked():
            raise HTTPException(409, "A PDF export is already running. Wait for it to finish.")
        async with export_lock:
            try:
                data = await asyncio.wait_for(export_pdf(result.model_dump(mode="json")), timeout=90)
            except TimeoutError:
                raise HTTPException(504, "PDF export timed out. Try a smaller set.") from None
        filename = quote(result.title.replace("/", "-").replace("\\", "-") + ".pdf", safe="")
        return Response(data, media_type="application/pdf", headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"})

    @app.post("/api/study/generate")
    async def generate(request: GenerateRequest):
        if app.state.provider is None:
            raise HTTPException(503, "Set OPENAI_API_KEY in the server environment or .env file.")
        if generation_lock.locked():
            raise HTTPException(409, "A generation request is already running. Wait for it to finish.")
        async with generation_lock:
            return await generate_study(workspace, default_document.id, request, app.state.provider)

    @app.get("/source.pdf")
    def source_file():
        return FileResponse(source.path,media_type="application/pdf",filename=source.path.name,
                            content_disposition_type="inline")

    @app.get("/fonts/{filename}")
    def font_file(filename: str):
        if not re.fullmatch(r"pdf_[a-f0-9]{20}\.otf", filename):
            raise HTTPException(404,"Font not found")
        path=source.registry.directory/filename
        if not path.is_file():
            raise HTTPException(404,"Font not found")
        return FileResponse(path,media_type="font/otf")

    @app.get("/api/pages/{number}")
    def page(number: int):
        return source.page(number)

    @app.get("/api/pages/{number}/formulas")
    def page_formulas(number: int):
        page = source.page(number)
        return {"page": number, "warnings": page.warnings, "formulas": [
            source.select(number, candidate.bbox, f"Formula {index + 1}")
            for index, candidate in enumerate(page.candidates)
        ]}

    @app.post("/api/preview")
    def preview(selection: Selection):
        return source.select(selection.page,selection.bbox,selection.title)

    @app.get("/api/formulas")
    def formulas():
        return store.list()

    @app.post("/api/formulas",status_code=201)
    def save_formula(selection: Selection):
        return store.add(source.select(selection.page,selection.bbox,selection.title))

    @app.get("/api/formulas/{identifier}")
    def formula(identifier: str):
        return store.get(identifier)

    @app.post("/api/formulas/{identifier}/variants",status_code=201)
    def sign_variant(identifier: str,change: SignChange):
        return store.add(replace_sign(store.get(identifier),change.node_id,change.replacement))

    @app.patch("/api/formulas/{identifier}/review")
    def review(identifier: str,review: Review):
        record=store.get(identifier)
        if review.state=="accepted" and record.warnings:
            raise ValueError("Resolve extraction warnings before accepting this formula")
        return store.review(identifier,review)

    @app.get("/api/export")
    def export():
        result={"schema_version":1,"document":document(),
                "formulas":[f.model_dump(mode="json") for f in store.list()]}
        return Response(json.dumps(result,ensure_ascii=False,indent=2),media_type="application/json",
                        headers={"Content-Disposition":f'attachment; filename="formulas-{source.sha256[:8]}.json"'})

    app.mount("/static",StaticFiles(directory=static),name="static")
    return app


def main():
    import uvicorn
    parser=argparse.ArgumentParser(description="Generate study material and render editable mathematics locally")
    parser.add_argument("--pdf",type=Path,default=Path("main.pdf"))
    parser.add_argument("--data-dir",type=Path,default=Path(".formula-lab"))
    parser.add_argument("--port",type=int,default=8765)
    args=parser.parse_args()
    uvicorn.run(create_app(args.pdf,args.data_dir),host="127.0.0.1",port=args.port)
