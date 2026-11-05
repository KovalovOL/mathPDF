MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
DOCUMENT_SELECT = """SELECT d.*, e.original_document_id, COALESCE(e.revision,0) AS annotation_revision
                     FROM documents d LEFT JOIN document_edits e ON e.document_id=d.id AND e.owner_id=d.owner_id"""
