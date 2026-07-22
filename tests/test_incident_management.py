import pytest
from domain.models import AgentFinding, Incident, IncidentAnalysis, SimilarIncident
from agents.code_investigation import extract_error
from core.config import PROJECT_ROOT
from repositories.servicenow_repository import ServiceNowIncidentRepository
from services.incident_management import IncidentManagementService
from services.azure_openai import AzureOpenAIClient
from vector.in_memory_store import cosine_similarity
from vector.azure_ai_search_store import AzureAISearchIncidentStore
from services.analysis_sessions import AnalysisChatService, AnalysisSessionStore, IncidentToolRegistry

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
        async def investigate(self, _incident: Incident) -> AgentFinding:
            return AgentFinding(agentName="CodeInvestigationAgent", status="CODE_EVIDENCE_FOUND", summary="Found code", evidence="file.py")
    service = IncidentManagementService(Store(), Advisor(), DeploymentAgent(), CodeAgent())
    result = await service.analyze(incident("reporting-api"))
    assert result.agent_findings[0].status == "DEPLOYMENT_FOUND"
    assert result.recommendation == "Investigate the release."

def test_error_extraction_prefers_exception_from_logs() -> None:
    logs = "INFO export started\nERROR TimestampFormatError: completed_at is a string\nAttributeError: 'str' object has no attribute 'strftime'"
    assert extract_error(logs) == "AttributeError: 'str' object has no attribute 'strftime'"



def test_servicenow_record_maps_to_historical_incident() -> None:
    result = ServiceNowIncidentRepository._to_incident(
        {
            "number": "INC0010001",
            "short_description": "Checkout requests return 502",
            "description": "Users cannot complete checkout after release 2.14.0.",
            "close_notes": "Rolled back the release.",
            "close_code": "Software defect",
            "priority": "2 - High",
            "cmdb_ci": "checkout-api",
            "sys_created_on": "2026-07-20 09:00:00",
            "resolved_at": "2026-07-20 10:00:00",
            "sys_updated_on": "2026-07-20 10:30:00",
        }
    )
    assert result.id == "INC0010001"
    assert result.service == "checkout-api"
    assert result.severity == "P2"
    assert result.resolution == "Rolled back the release."
    assert result.attachments == []
    assert result.model_dump(by_alias=True) == {
        "id": "INC0010001",
        "title": "Checkout requests return 502",
        "service": "checkout-api",
        "severity": "P2",
        "symptoms": "Users cannot complete checkout after release 2.14.0.",
        "createdAt": "2026-07-20 09:00:00",
        "resolvedAt": "2026-07-20 10:00:00",
        "updatedAt": "2026-07-20 10:30:00",
        "rootCause": "Software defect",
        "resolution": "Rolled back the release.",
        "logs": None,
        "attachments": [],
    }


def test_servicenow_loads_file_content_only_for_txt_attachments(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __init__(self, payload: dict | None = None, content: bytes = b"") -> None:
            self._payload = payload or {}
            self.content = content

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return self._payload

    calls: list[str] = []

    def fake_get(url: str, **_kwargs: object) -> Response:
        calls.append(url)
        if url.endswith("/sys_attachment"):
            return Response(
                {
                    "result": [
                        {
                            "sys_id": "text-file-id",
                            "table_sys_id": "incident-id",
                            "file_name": "diagnostics.TXT",
                            "content_type": "text/plain",
                            "size_bytes": "18",
                        },
                        {
                            "sys_id": "pdf-file-id",
                            "table_sys_id": "incident-id",
                            "file_name": "report.pdf",
                            "content_type": "application/pdf",
                            "size_bytes": "42",
                        },
                    ]
                }
            )
        assert url.endswith("/attachment/text-file-id/file")
        return Response(content=b"Connection timed out")

    monkeypatch.setattr("repositories.servicenow_repository.httpx.get", fake_get)
    repository = ServiceNowIncidentRepository("https://instance.example", "user", "password")

    attachments = repository._load_attachments(["incident-id"])["incident-id"]

    assert [attachment.model_dump(by_alias=True) for attachment in attachments] == [
        {
            "id": "text-file-id",
            "fileName": "diagnostics.TXT",
            "contentType": "text/plain",
            "sizeBytes": 18,
            "fileContent": "Connection timed out",
        },
        {
            "id": "pdf-file-id",
            "fileName": "report.pdf",
            "contentType": "application/pdf",
            "sizeBytes": 42,
            "fileContent": None,
        },
    ]
    assert calls == [
        "https://instance.example/api/now/table/sys_attachment",
        "https://instance.example/api/now/attachment/text-file-id/file",
    ]



def test_servicenow_record_maps_to_historical_incident() -> None:
    result = ServiceNowIncidentRepository._to_incident(
        {
            "number": "INC0010001",
            "short_description": "Checkout requests return 502",
            "description": "Users cannot complete checkout after release 2.14.0.",
            "close_notes": "Rolled back the release.",
            "close_code": "Software defect",
            "priority": "2 - High",
            "cmdb_ci": "checkout-api",
            "sys_created_on": "2026-07-20 09:00:00",
            "resolved_at": "2026-07-20 10:00:00",
            "sys_updated_on": "2026-07-20 10:30:00",
        }
    )
    assert result.id == "INC0010001"
    assert result.service == "checkout-api"
    assert result.severity == "P2"
    assert result.resolution == "Rolled back the release."
    assert result.attachments == []
    assert result.model_dump(by_alias=True) == {
        "id": "INC0010001",
        "title": "Checkout requests return 502",
        "service": "checkout-api",
        "severity": "P2",
        "symptoms": "Users cannot complete checkout after release 2.14.0.",
        "createdAt": "2026-07-20 09:00:00",
        "resolvedAt": "2026-07-20 10:00:00",
        "updatedAt": "2026-07-20 10:30:00",
        "rootCause": "Software defect",
        "resolution": "Rolled back the release.",
        "logs": None,
        "attachments": [],
    }


def test_servicenow_loads_file_content_only_for_txt_attachments(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __init__(self, payload: dict | None = None, content: bytes = b"") -> None:
            self._payload = payload or {}
            self.content = content

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return self._payload

    calls: list[str] = []

    def fake_get(url: str, **_kwargs: object) -> Response:
        calls.append(url)
        if url.endswith("/sys_attachment"):
            return Response(
                {
                    "result": [
                        {
                            "sys_id": "text-file-id",
                            "table_sys_id": "incident-id",
                            "file_name": "diagnostics.TXT",
                            "content_type": "text/plain",
                            "size_bytes": "18",
                        },
                        {
                            "sys_id": "pdf-file-id",
                            "table_sys_id": "incident-id",
                            "file_name": "report.pdf",
                            "content_type": "application/pdf",
                            "size_bytes": "42",
                        },
                    ]
                }
            )
        assert url.endswith("/attachment/text-file-id/file")
        return Response(content=b"Connection timed out")

    monkeypatch.setattr("repositories.servicenow_repository.httpx.get", fake_get)
    repository = ServiceNowIncidentRepository("https://instance.example", "user", "password")

    attachments = repository._load_attachments(["incident-id"])["incident-id"]

    assert [attachment.model_dump(by_alias=True) for attachment in attachments] == [
        {
            "id": "text-file-id",
            "fileName": "diagnostics.TXT",
            "contentType": "text/plain",
            "sizeBytes": 18,
            "fileContent": "Connection timed out",
        },
        {
            "id": "pdf-file-id",
            "fileName": "report.pdf",
            "contentType": "application/pdf",
            "sizeBytes": 42,
            "fileContent": None,
        },
    ]
    assert calls == [
        "https://instance.example/api/now/table/sys_attachment",
        "https://instance.example/api/now/attachment/text-file-id/file",
    ]


async def test_azure_openai_client_parses_embedding_and_chat_responses() -> None:
    client = AzureOpenAIClient(
        endpoint="https://example.openai.azure.com",
        api_key="test-key",
        api_version="2024-10-21",
        embedding_deployment="embedding-deployment",
        chat_deployment="chat-deployment",
    )

    async def fake_request(path: str, _payload: dict, timeout: float) -> dict:
        assert timeout in (90, 120)
        if path.endswith("/embeddings"):
            return {"data": [{"embedding": [0.1, 0.2]}]}
        return {"choices": [{"message": {"content": "Investigate the release."}}]}

    client._request = fake_request  # type: ignore[method-assign]
    assert await client.embed("incident text") == [0.1, 0.2]
    assert await client.generate("prompt") == "Investigate the release."


async def test_azure_ai_search_store_uses_hybrid_text_vector_query() -> None:
    store = AzureAISearchIncidentStore(
        endpoint="https://example.search.windows.net",
        api_key="test-key",
        index_name="historical-incidents",
        api_version="2025-09-01",
    )

    async def fake_request(payload: dict) -> dict:
        assert payload["searchFields"] == "title,symptoms,service,content"
        assert payload["vectorQueries"][0]["kind"] == "text"
        assert payload["vectorQueries"][0]["fields"] == "contentVector"
        return {"@odata.count": 1, "value": [{
            "id": "INC-OLD-1", "title": "Old timeout", "service": "checkout-api",
            "severity": "SEV-2", "symptoms": "Gateway timeout", "rootCause": "Bad pool",
            "resolution": "Restarted safely", "@search.score": 0.021,
        }]}

    store._request = fake_request  # type: ignore[method-assign]
    matches = await store.search(incident(), 3)
    assert matches[0].incident.id == "INC-OLD-1"
    assert matches[0].similarity == pytest.approx(0.021)
    assert store.count == 1


async def test_analysis_session_is_temporary_and_removed_on_delete() -> None:
    store = AnalysisSessionStore()
    analysis = IncidentAnalysis(
        incomingIncident=incident(), similarIncidents=[], agentFindings=[], recommendation="Check evidence."
    )
    session_id = await store.create(analysis)
    assert (await store.get(session_id)) is not None
    assert await store.delete(session_id) is True
    assert await store.get(session_id) is None


async def test_chat_executes_only_registered_tool_and_returns_its_source() -> None:
    class Store:
        async def search(self, _incident: Incident, _limit: int) -> list[SimilarIncident]:
            return [SimilarIncident(incident=Incident(id="INC-OLD-1", title="Old", service="checkout-api", severity="SEV-2", symptoms="timeout"), similarity=0.9)]

    class DeploymentAgent:
        def investigate(self, _incident: Incident) -> AgentFinding:
            return AgentFinding(agentName="DeploymentCheckAgent", status="DEPLOYMENT_FOUND", summary="Found", evidence="deploymentId=DEP-1")

    class CodeRepository:
        def search(self, _query: str, limit: int = 3):
            return []

    class Client:
        def __init__(self) -> None:
            self.call_count = 0
        async def chat_with_tools(self, _messages, tools):
            self.call_count += 1
            assert {tool["function"]["name"] for tool in tools} == {
                "search_historical_incidents", "get_deployment_evidence", "get_code_evidence", "inspect_code_change_impact", "run_deep_rca_evidence"
            }
            if self.call_count == 1:
                return {"message": {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1", "function": {"name": "search_historical_incidents", "arguments": '{"investigation_focus":"prior resolutions"}'}}]}}
            return {"message": {"role": "assistant", "content": "A prior incident exists.", "tool_calls": []}}

    sessions = AnalysisSessionStore()
    analysis = IncidentAnalysis(incomingIncident=incident(), similarIncidents=[], agentFindings=[], recommendation="Initial")
    session_id = await sessions.create(analysis)
    chat = AnalysisChatService(sessions, IncidentToolRegistry(Store(), DeploymentAgent(), CodeRepository()), Client())
    response = await chat.chat(session_id, "Have we seen this before?")
    assert response is not None
    assert response.answer == "A prior incident exists."
    assert response.agent_calls == ["search_historical_incidents"]
    assert response.sources == ["INC-OLD-1"]
