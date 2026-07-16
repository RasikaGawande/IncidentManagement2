"""Extracts an error from logs and connects it to relevant code evidence."""

import re

from domain.models import AgentFinding, Incident
from repositories.code_repository import CodeRepository


class CodeInvestigationAgent:
    """Runs only for low-similarity incidents that include application logs."""

    def __init__(self, code_repository: CodeRepository) -> None:
        self._code_repository = code_repository

    def investigate(self, incident: Incident) -> AgentFinding:
        error = extract_error(incident.logs or "")
        if error is None:
            return AgentFinding(
                agentName="CodeInvestigationAgent",
                status="NO_ERROR_EXTRACTED",
                summary="Logs were supplied but no actionable error signature was found.",
                evidence="Provide stack traces or ERROR-level log entries for a code investigation.",
            )

        try:
            matches = self._code_repository.search(error)
        except RuntimeError as error:
            return AgentFinding(
                agentName="CodeInvestigationAgent",
                status="BACKEND_UNAVAILABLE",
                summary=f"Extracted error signature: {error}",
                evidence="Code search could not be completed; investigate the repository manually.",
            )
        if not matches:
            return AgentFinding(
                agentName="CodeInvestigationAgent",
                status="CODE_NOT_FOUND",
                summary=f"Extracted error signature: {error}",
                evidence="No matching source was found in the configured code repository.",
            )

        evidence = "\n\n".join(f"{match.path}:\n{match.excerpt}" for match in matches)
        return AgentFinding(
            agentName="CodeInvestigationAgent",
            status="CODE_EVIDENCE_FOUND",
            summary=f"Extracted error signature: {error}",
            evidence=evidence,
        )


def extract_error(logs: str) -> str | None:
    """Return the most specific exception/error line from application logs."""
    lines = [line.strip() for line in logs.splitlines() if line.strip()]
    patterns = (
        r"(?:[A-Za-z_][\w.]*)(?:Exception|Error):\s*.+",
        r"ERROR\s+.+",
    )
    for pattern in patterns:
        for line in reversed(lines):
            match = re.search(pattern, line)
            if match:
                return match.group(0)[-500:]
    return None
