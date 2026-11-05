"""Private immutable report binaries and downloadable ZIP projection."""

import io
import json
import zipfile
from pathlib import Path
from botocore.exceptions import ClientError
from app.core.serialization import bounded, MAX_CONTEXT_BYTES


class ReportBundles:

    def __init__(self, storage):
        self._storage = storage

    def collect(self, report):
        manifest = json.loads(report["manifest"])
        manifest["files"] = [
            self._copy_report_source(report, source)
            for source in manifest.get("sources", [])
        ]
        self._write_report_snapshot(report, manifest)
        return manifest

    def export(self, report):
        if report["collection_status"] != "ready":
            raise ValueError(
                "This report is still collecting context. Try again shortly."
            )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "report.json", json.dumps(report, ensure_ascii=False, indent=2)
            )
            for entry in report["manifest"].get("files", []):
                if entry["status"] == "available":
                    path = self._storage.path(entry["key"], entry["sha256"])
                    archive.write(
                        path,
                        "files/"
                        + entry["document_id"]
                        + "/"
                        + Path(entry["filename"]).name,
                    )
        return buffer.getvalue()

    def _copy_report_source(self, report, source):
        target = (
            "reports/"
            + report["id"]
            + "/files/"
            + source["id"]
            + "/"
            + Path(source["stored_name"]).name
        )
        entry = {
            "document_id": source["id"],
            "filename": source["filename"],
            "sha256": source["sha256"],
            "key": target,
        }
        try:
            self._copy_source_revision(source, target)
            entry["status"] = "available"
        except ClientError as error:
            if str(error.response.get("Error", {}).get("Code")) not in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                raise
            entry["status"] = "unavailable"
            entry["reason"] = "The source was deleted before collection."
        except (FileNotFoundError, ValueError):
            entry["status"] = "unavailable"
            entry["reason"] = "The source version is missing or invalid."
        return entry

    def _write_report_snapshot(self, report, manifest):
        packet = {
            "report": {
                k: report[k]
                for k in [
                    "id",
                    "user_id",
                    "origin",
                    "category",
                    "comment",
                    "request_id",
                    "created_at",
                ]
            },
            "context": json.loads(report["payload"]),
            "manifest": manifest,
        }
        self._storage.put(
            "reports/" + report["id"] + "/context.json",
            json.dumps(
                bounded(packet, 8 * MAX_CONTEXT_BYTES), ensure_ascii=False
            ).encode(),
            "application/json",
        )

    def _copy_source_revision(self, source, target):
        try:
            self._storage.copy(
                "documents/" + source["stored_name"], target, source["sha256"]
            )
        except ClientError as error:
            if str(error.response.get("Error", {}).get("Code")) not in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                raise
            self._storage.copy(
                "report-source-cache/" + source["stored_name"], target, source["sha256"]
            )
        except (FileNotFoundError, ValueError):
            self._storage.copy(
                "report-source-cache/" + source["stored_name"], target, source["sha256"]
            )
