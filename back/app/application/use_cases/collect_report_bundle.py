"""Lease one report and capture its referenced immutable source revisions."""


class CollectReportBundle:
    def __init__(self, reports, bundles, cleanup, usage):
        self._reports, self._bundles = reports, bundles
        self._cleanup, self._usage = cleanup, usage

    def execute(self) -> bool:
        self._usage.flush_spool()
        self._reports.flush_spool()
        claimed = self._reports.claim_collection()
        if claimed is None:
            return False
        report, lease = claimed
        try:
            manifest = self._bundles.collect(report)
            if self._reports.complete_collection(report, lease, manifest):
                self._cleanup.execute(
                    [s["stored_name"] for s in manifest.get("sources", [])]
                )
            return True
        except Exception as error:
            return self._reports.retry_collection(report, lease, error)
