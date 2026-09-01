from sqlalchemy.orm import Session
from app.providers.checks import CheckProvider, CheckRunReport


class LocalCheckProvider(CheckProvider):
    """
    Local substrate check reporter.
    For local Git repositories, check status is recorded internally
    within SUTRA database records without external HTTP API dispatch.
    """

    def __init__(self, db: Session):
        self.db = db

    def report_check_run(
        self,
        owner: str,
        name: str,
        report: CheckRunReport,
    ) -> str:
        # For local repositories, check runs are represented by SUTRA PolicyDecisions
        return f"local-check:{report.head_sha[:10]}:{report.status.value}"
