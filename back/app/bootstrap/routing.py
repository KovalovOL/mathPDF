from app.study.service import StudyQuery
from app.application.use_cases.start_generation import StartGeneration
from app.application.use_cases.cancel_generation import CancelGeneration
from app.application.use_cases.generate_study_now import GenerateStudyNow
from app.application.use_cases.preview_document_deletion import PreviewDocumentDeletion
from app.application.use_cases.delete_document import DeleteDocument
from app.application.use_cases.rename_library_item import RenameLibraryItem
from app.application.use_cases.validate_study_set import ValidateStudySet
from app.application.use_cases.save_study_set import SaveStudySet
from app.application.use_cases.export_study_set import ExportStudySet
from app.application.use_cases.start_review import StartReview
from app.infrastructure.documents.cleanup import BinaryCleanup
from app.infrastructure.export.browser import export_pdf
from app.documents.handler import DocumentsHandler
from app.identity.handler import IdentityHandler
from app.library.handler import LibraryHandler
from app.study.handler import StudyHandler
from app.generation.handler import GenerationHandler
from app.reviews.handler import ReviewsHandler
from app.reports.handler import DiagnosticsHandler
from app.infrastructure.http.errors import ErrorHandlers
from app.infrastructure.http.gateway import GatewayHandler
from app.core.observability.diagnostics import ClientReportLimit


def register_handlers(app, runtime):
    s = runtime.services
    preview = PreviewDocumentDeletion(s.deletion)
    delete = DeleteDocument(s.deletion, BinaryCleanup(s.persistence))
    validator = ValidateStudySet(s.sets, s.documents)
    saver = SaveStudySet(validator, s.sets)
    exporter = ExportStudySet(validator, export_pdf, runtime.export_lock)
    handlers = [
        IdentityHandler(s.auth),
        DocumentsHandler(
            s.documents, s.annotation_reader, s.annotation_saver, preview, delete
        ),
        LibraryHandler(s.library, s.library_snapshot, RenameLibraryItem(s.rename)),
        StudyHandler(StudyQuery(s.sets), saver, exporter, preview, delete),
        GenerationHandler(
            runtime.provider is not None,
            s.usage.quota,
            runtime.jobs,
            StartGeneration(s.usage, runtime.jobs, runtime.provider),
            CancelGeneration(runtime.jobs),
            GenerateStudyNow(
                runtime.generator, runtime.provider, runtime.generation_lock
            ),
        ),
        ReviewsHandler(s.reviews, StartReview(s.reviews, s.sets, s.documents)),
        DiagnosticsHandler(ClientReportLimit()),
        GatewayHandler(s.persistence, s.auth, s.documents, s.sets),
    ]
    for handler in handlers:
        handler.register(app)


def register_errors(app):
    ErrorHandlers().register(app)
