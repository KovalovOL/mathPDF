from app.infrastructure.documents.preparation import SelectedDocumentPreparation
from app.infrastructure.providers.prompts import PromptLoader, PROMPTS
from app.generation.service import GenerationService

"""Compatibility fixture for historical checks; never imported by application code."""
from pathlib import Path
from app.bootstrap.container import Services
from app.infrastructure.documents.cleanup import BinaryCleanup
from app.application.use_cases.delete_document import DeleteDocument
from app.application.use_cases.generate_study import GenerateStudy


class Workspace:
    def __init__(self, directory: Path, services=None):
        self.services = services or Services.create(directory)
        self.usage = self.services.usage
        self.reports = self.services.reports
        self.db = self.services.persistence.db
        self.storage = self.services.persistence.storage
        self.files = self.services.persistence.files
        self.directory = self.services.persistence.directory
        self.database = self.services.persistence.database

    def connection(self):
        return self.services.persistence.connection()

    def add_document(self, filename, data, owner_id):
        return self.services.documents.add_document(filename, data, owner_id)

    def document(self, identifier, owner):
        return self.services.documents.document(identifier, owner)

    def documents(self, owner):
        return self.services.documents.documents(owner)

    def path(self, identifier, owner):
        return self.services.documents.path(identifier, owner)

    def save_set(self, result, owner):
        return self.services.sets.save_set(result, owner)

    def sets(self, owner):
        return self.services.sets.sets(owner)

    def study_set(self, identifier, owner):
        return self.services.sets.study_set(identifier, owner)

    def rename_item(self, kind, identifier, owner, request):
        return self.services.rename.rename_item(kind, identifier, owner, request)

    def check_set_owner(self, identifier, owner):
        return self.services.sets.check_set_owner(identifier, owner)

    def annotation_state(self, identifier, owner):
        return self.services.annotation_reader.execute(identifier, owner)

    def save_annotations(self, identifier, owner, request):
        return self.services.annotation_saver.execute(identifier, owner, request)

    def deletion_info(self, kind, identifier, owner):
        return self.services.deletion.deletion_info(kind, identifier, owner)

    def delete(self, kind, identifier, owner, revision):
        use_case = DeleteDocument(
            self.services.deletion, BinaryCleanup(self.services.persistence)
        )
        return use_case.execute(kind, identifier, owner, revision)

    def _cleanup_binaries(self, names):
        return BinaryCleanup(self.services.persistence).execute(names)


def workspace_for(app):
    return Workspace(app.state.services.persistence.directory, app.state.services)


async def generate_study(workspace, owner, selection, provider, progress=None):
    return await GenerateStudy(
        SelectedDocumentPreparation(workspace.services.documents),
        GenerationService(PromptLoader()),
        workspace.usage,
    ).execute(owner, selection, provider, progress)


async def collect_study(documents, request, provider, progress):
    return await GenerationService(PromptLoader()).collect(
        documents, request, provider, progress
    )


def load_prompts(request, documents):
    return PromptLoader().load(request, documents)
