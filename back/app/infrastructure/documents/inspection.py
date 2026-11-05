import io
import re
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from app.documents.constants import MEDIA_TYPES, MAX_UPLOAD_BYTES
from app.documents.ports import InspectedUpload


class UploadInspector:
    def inspect(self, filename: str, data: bytes, owner_id: str) -> InspectedUpload:
        if not re.fullmatch(r"[a-f0-9]{32}", owner_id):
            raise ValueError("Invalid account identifier.")
        filename = Path(filename.replace("\\", "/")).name[:200]
        suffix = Path(filename).suffix.lower()
        media_type = MEDIA_TYPES.get(suffix)
        if not media_type:
            raise ValueError("Choose a PDF, TXT, Markdown, PNG, JPEG, or WebP file.")
        if not data or len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("Each file must contain data and be no larger than 25 MB.")
        pages = None
        if suffix == ".pdf":
            pages = self._pdf(data)
        elif media_type.startswith("image/"):
            self._image(data, media_type)
        else:
            self._text(data)
        return InspectedUpload(filename, suffix, media_type, pages)

    @staticmethod
    def _pdf(data: bytes) -> int:
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValueError("Password-protected PDFs are not supported.")
            if not reader.pages:
                raise ValueError("The PDF has no pages.")
            return len(reader.pages)
        except ValueError:
            raise
        except Exception:
            raise ValueError("This file could not be read as a PDF.") from None

    @staticmethod
    def _image(data: bytes, media_type: str) -> None:
        try:
            with Image.open(io.BytesIO(data)) as image:
                expected = {
                    "image/png": "PNG",
                    "image/jpeg": "JPEG",
                    "image/webp": "WEBP",
                }[media_type]
                if image.format != expected or image.width * image.height > 40_000_000:
                    raise ValueError("Use a valid image no larger than 40 megapixels.")
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ValueError("This image could not be read.") from None

    @staticmethod
    def _text(data: bytes) -> None:
        if len(data) > 1024 * 1024:
            raise ValueError("Text context files must be no larger than 1 MB.")
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("Save text and Markdown files as UTF-8.") from None
        if b"\x00" in data:
            raise ValueError("This file is not a supported text document.")
