import argparse
from pathlib import Path
import uvicorn
from app.bootstrap.api import create_app


def main():
    parser = argparse.ArgumentParser(description="Run the Acadence backend")
    parser.add_argument("--data-dir", type=Path, default=Path(".formula-lab"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run(
        create_app(args.data_dir), host=args.host, port=args.port, access_log=False
    )
