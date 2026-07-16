import pytest
from domain.models import AgentFinding, Incident, SimilarIncident
from agents.code_investigation import CodeInvestigationAgent, extract_error
from core.config import PROJECT_ROOT
from repositories.code_repository import JsonCodeRepository
from services.incident_management import IncidentManagementService
from vector.in_memory_store import cosine_similarity

def incident(service: str = "checkout-api") -> Incident:
    return Incident(id="INC-1", title="Timeout", service=service, severity="SEV-1", symptoms="Requests time out")

def test_cosine_similarity_returns_one_for_identical_vectors() -> None:
    assert cosine_similarity([1.0, 2.0], [1.0, 2.0]) == pytest.approx(1.0)

async def test_low_similarity_runs_deployment_agent() -> None:
    class Store:
        async def search(self, _incident: Incident, _limit: int) -> list[SimilarIncident]:
            return [SimilarIncident(incident=incident(), similarity=0.4)]
    class Advisor:
        async def recommend(self, _incoming, _matches, findings) -> str:
            assert len(findings) == 1
            return "Investigate the release."
    class DeploymentAgent:
        def investigate(self, _incident: Incident) -> AgentFinding:
            return AgentFinding(agentName="DeploymentCheckAgent", status="DEPLOYMENT_FOUND", summary="Found one", evidence="DEP-1")
    class CodeAgent:
        def investigate(self, _incident: Incident) -> AgentFinding:
            return AgentFinding(agentName="CodeInvestigationAgent", status="CODE_EVIDENCE_FOUND", summary="Found code", evidence="file.py")
    service = IncidentManagementService(Store(), Advisor(), DeploymentAgent(), CodeAgent(), 0.85)
    result = await service.analyze(incident("reporting-api"))
    assert result.agent_findings[0].status == "DEPLOYMENT_FOUND"
    assert result.recommendation == "Investigate the release."

def test_error_extraction_prefers_exception_from_logs() -> None:
    logs = "INFO export started\nERROR TimestampFormatError: completed_at is a string\nAttributeError: 'str' object has no attribute 'strftime'"
    assert extract_error(logs) == "AttributeError: 'str' object has no attribute 'strftime'"

def test_code_agent_finds_simulated_source_for_log_error() -> None:
    agent = CodeInvestigationAgent(JsonCodeRepository(PROJECT_ROOT / "data"))
    result = agent.investigate(
        incident().model_copy(update={"logs": "AttributeError: 'str' object has no attribute 'strftime'"})
    )
    assert result.status == "CODE_EVIDENCE_FOUND"
    assert "reporting/jobs/report_export.py" in result.evidence
