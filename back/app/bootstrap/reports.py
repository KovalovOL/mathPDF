from app.reports.repository import ReportRepository
from app.reports.service import Reports
from app.infrastructure.reports.bundles import ReportBundles
from app.infrastructure.http.frontend import build_id
from app.application.use_cases.collect_report_bundle import CollectReportBundle


def create_reports(persistence, usage, cleanup):
    repository = ReportRepository(persistence, build_id())
    bundles = ReportBundles(persistence.storage)
    collector = CollectReportBundle(repository, bundles, cleanup, usage)
    return Reports(repository, collector, bundles)
