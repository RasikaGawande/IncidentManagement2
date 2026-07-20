"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request

from agents.deployment_check import DeploymentCheckAgent
from agents.code_investigation import CodeInvestigationAgent
from core.config import Settings
from domain.models import AnalyzeRequest, HealthResponse, IncidentAnalysis
from repositories.json_repository import DeploymentHistoryRepository, JsonIncidentRepository
from repositories.servicenow_repository import ServiceNowIncidentRepository
from repositories.code_repository import GithubCodeRepository, JsonCodeRepository
from services.advisor import IncidentAdvisor
from services.incident_management import IncidentManagementService
from services.azure_openai import AzureOpenAIClient
from vector.in_memory_store import InMemoryIncidentVectorStore

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings.from_environment()
    repository = (
        ServiceNowIncidentRepository(
            settings.servicenow_instance_url,
            settings.servicenow_username,
            settings.servicenow_password,
            settings.servicenow_incident_limit,
        )
        if settings.servicenow_instance_url
        else JsonIncidentRepository(settings.data_directory)
    )
    incidents = repository.load_historical_incidents()
    azure_openai = AzureOpenAIClient(
        endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        embedding_deployment=settings.azure_openai_embedding_deployment,
        chat_deployment=settings.azure_openai_chat_deployment,
    )
    vector_store = await InMemoryIncidentVectorStore.build(incidents, azure_openai)
    code_repository = (
        GithubCodeRepository(settings.github_repository, settings.github_token)
        if settings.github_repository and settings.github_token
        else JsonCodeRepository(settings.data_directory)
    )
    app.state.incident_service = IncidentManagementService(
        vector_store=vector_store,
        advisor=IncidentAdvisor(azure_openai),
        deployment_agent=DeploymentCheckAgent(
            DeploymentHistoryRepository(settings.data_directory)
        ),
        code_agent=CodeInvestigationAgent(code_repository),
        similarity_threshold=settings.similarity_threshold,
    )
    app.state.historical_incident_count = vector_store.count
    yield

app = FastAPI(title="Incident Management API", version="1.0.0", lifespan=lifespan)


def service_from(request: Request) -> IncidentManagementService:
    return request.app.state.incident_service

@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", historicalIncidentCount=request.app.state.historical_incident_count)

@app.post("/api/v1/incidents/analyze", response_model=IncidentAnalysis, tags=["incidents"])
async def analyze_incident(payload: AnalyzeRequest, request: Request) -> IncidentAnalysis:
    try:
        return await service_from(request).analyze(payload.incident, payload.limit)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
