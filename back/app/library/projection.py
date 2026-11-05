import json
import logging


class LibraryProjection:

    def render(self, snapshot):
        files, sets, metadata, folders = (
            snapshot.files,
            snapshot.sets,
            snapshot.metadata,
            snapshot.folders,
        )
        by_id = {file.id: file for file in files}
        result = [self._study_item(item, by_id, metadata) for item in sets]
        return {
            "folders": folders,
            "files": [
                self._place("documents", d.model_dump(), metadata) for d in files
            ],
            "sets": result,
        }

    def _place(self, kind, item, metadata):
        state = metadata.get((kind, item["id"]), {})
        return {
            **item,
            "folder_id": state.get("folder_id"),
            "archived": bool(state.get("archived", False)),
        }

    def _study_item(self, item, by_id, metadata):
        try:
            payload = json.loads(item.pop("payload"))
        except (ValueError, TypeError):
            payload = {}
            item["metadata_error"] = "unreadable_study_metadata"
            logging.getLogger(__name__).warning(
                "Study metadata is unreadable",
                extra={
                    "event": "library.metadata_invalid",
                    "error_code": "invalid_study_payload",
                    "study_set_id": item["id"],
                },
            )
        source = payload.get("document", {}) if isinstance(payload, dict) else {}
        if not isinstance(source, dict):
            source = {}
        item["document_id"], item["document_filename"] = (
            source.get("id"),
            source.get("filename"),
        )
        try:
            difficulty = (
                int(payload.get("difficulty", 3)) if isinstance(payload, dict) else 3
            )
        except (TypeError, ValueError):
            difficulty = 3
        item["difficulty"] = difficulty
        doc = by_id.get(item["document_id"])
        return self._place(
            "study-sets",
            {
                **item,
                "document_filename": doc.filename if doc else item["document_filename"],
            },
            metadata,
        )
