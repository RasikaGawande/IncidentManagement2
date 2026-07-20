"""Orchestrates similarity search, evidence collection, and recommendations."""

from agents.deployment_check import DeploymentCheckAgent
from agents.code_investigation import CodeInvestigationAgent
from domain.models import Incident, IncidentAnalysis
from services.advisor import IncidentAdvisor
from vector.in_memory_store import InMemoryIncidentVectorStore

class IncidentManagementService:
    def __init__(
        self,
        vector_store: InMemoryIncidentVectorStore,
        advisor: IncidentAdvisor,
        deployment_agent: DeploymentCheckAgent,
        code_agent: CodeInvestigationAgent,
        similarity_threshold: float,
    ) -> None:
        self._vector_store = vector_store
        self._advisor = advisor
        self._deployment_agent = deployment_agent
        self._code_agent = code_agent
        self._similarity_threshold = similarity_threshold
    async def analyze(self, incident: Incident, limit: int = 3) -> IncidentAnalysis:
        matches = await self._vector_store.search(incident, limit)
        findings = []
        has_strong_match = matches and matches[0].similarity >= self._similarity_threshold
        if not has_strong_match:
            findings.append(self._deployment_agent.investigate(incident))
            if incident.logs:
                findings.append(self._code_agent.investigate(incident))
        recommendation = await self._advisor.recommend(incident, matches, findings)
        return IncidentAnalysis(
            incomingIncident=incident,
            similarIncidents=matches,
            agentFindings=findings,
            recommendation=recommendation,
        )

    def historical_incidents(self) -> list[Incident]:
        """Return the current historical data source without embedding metadata."""
        return self._vector_store.incidents
