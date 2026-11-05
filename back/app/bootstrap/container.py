from app.infrastructure.database.connection import INTEGRITY_ERRORS
from app.application.use_cases.get_document_annotations import GetDocumentAnnotations
from app.application.use_cases.save_document_annotations import SaveDocumentAnnotations
from app.infrastructure.documents.overlay import PdfAnnotationRenderer
from dataclasses import dataclass
from pathlib import Path
from app.infrastructure.persistence import PersistenceContext
from app.infrastructure.database.schema import initialize
from app.documents.repository import DocumentRepository
from app.documents.service import DocumentService
from app.infrastructure.documents.inspection import UploadInspector
from app.documents.deletion_repository import DeletionRepository
from app.infrastructure.documents.cleanup import BinaryCleanup
from app.identity.repository import UserRepository
from app.identity.authentication import Authentication
from app.identity.session_repository import SessionRepository
from app.identity.roles import Roles
from app.identity.role_repository import RoleRepository
from app.infrastructure.identity.config import read_auth_config
from app.infrastructure.identity.google import GoogleIdentityProvider
from app.annotations.repository import AnnotationRepository
from app.study.repository import StudySetRepository
from app.library.repository import LibraryRepository
from app.library.service import LibraryService
from app.application.use_cases.get_library_snapshot import GetLibrarySnapshot
from app.library.rename_repository import RenameRepository
from app.usage.service import Usage
from app.bootstrap.usage import create_usage
from app.reviews.service import Reviews
from app.reviews.repository import ReviewRepository
from app.reports.service import Reports
from app.bootstrap.reports import create_reports


@dataclass(frozen=True, slots=True)
class Services:
    persistence: PersistenceContext
    documents: DocumentService
    sets: StudySetRepository
    auth: Authentication
    annotations: AnnotationRepository
    annotation_reader: GetDocumentAnnotations
    annotation_saver: SaveDocumentAnnotations
    deletion: DeletionRepository
    library: LibraryService
    library_snapshot: GetLibrarySnapshot
    rename: RenameRepository
    usage: Usage
    reviews: Reviews
    reports: Reports
    users: UserRepository

    @classmethod
    def create(cls, directory: Path):
        persistence = PersistenceContext(directory)
        initialize(persistence)
        usage = create_usage(persistence)
        cleanup = BinaryCleanup(persistence)
        documents = DocumentService(DocumentRepository(persistence), UploadInspector())
        annotations = AnnotationRepository(persistence)
        reader = GetDocumentAnnotations(documents, annotations)
        saver = SaveDocumentAnnotations(
            reader, documents, annotations, PdfAnnotationRenderer(), cleanup
        )
        library = LibraryRepository(persistence, INTEGRITY_ERRORS)
        return cls(
            persistence=persistence,
            documents=documents,
            sets=StudySetRepository(persistence),
            auth=Authentication(
                SessionRepository(persistence),
                read_auth_config(),
                Roles(RoleRepository(persistence)),
                GoogleIdentityProvider(),
            ),
            annotations=annotations,
            annotation_reader=reader,
            annotation_saver=saver,
            deletion=DeletionRepository(persistence),
            library=LibraryService(library),
            library_snapshot=GetLibrarySnapshot(library),
            rename=RenameRepository(persistence),
            usage=usage,
            reviews=Reviews(ReviewRepository(persistence)),
            reports=create_reports(persistence, usage, cleanup),
            users=UserRepository(persistence),
        )
