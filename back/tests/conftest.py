from pathlib import Path
import pytest
from app.infrastructure.formula_extraction.reader import PdfSource


@pytest.fixture(scope="session")
def pdf_source(tmp_path_factory):
    path = Path(__file__).resolve().parents[2] / "main.pdf"
    if not path.exists():
        pytest.skip("The local sample PDF is not present")
    return PdfSource(path, tmp_path_factory.mktemp("source"))
