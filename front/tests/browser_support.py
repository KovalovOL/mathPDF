"""Browser binary configuration for frontend checks, independent of backend code."""

import os
import shutil
from pathlib import Path


def chromium_executable() -> str | None:
    configured = os.getenv("MATHPDF_CHROMIUM_EXECUTABLE")
    if configured:
        return configured
    for candidate in [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("google-chrome"),
    ]:
        if candidate and Path(candidate).is_file():
            return candidate
    return None
