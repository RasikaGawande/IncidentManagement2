"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import asyncio
import logging
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request

from agents.deployment_check import DeploymentCheckAgent
from agents.code_investigation import CodeInvestigationAgent
from core.config import Settings
from domain.models import AnalyzeRequest, HealthResponse, Incident, IncidentAnalysis
from repositories.json_repository import DeploymentHistoryRepository
from repositories.servicenow_repository import ServiceNowIncidentRepository
from repositories.code_repository import GithubCodeRepository, JsonCodeRepository
from services.advisor import IncidentAdvisor
from services.incident_management import IncidentManagementService
from services.azure_openai import AzureOpenAIClient
from vector.in_memory_store import InMemoryIncidentVectorStore

logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings.from_environment()
    if not settings.servicenow_instance_url:
        raise RuntimeError(
            "ServiceNow is required. Set SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, "
            "and SERVICENOW_PASSWORD."
        )
    repository = ServiceNowIncidentRepository(
        settings.servicenow_instance_url,
        settings.servicenow_username,
        settings.servicenow_password,
        settings.servicenow_incident_limit,
    )
    app.state.servicenow_repository = repository
    app.state.incident_service = None
    app.state.historical_incident_count = 0
    app.state.initialization_status = "starting"
    app.state.initialization_error = None
    app.state.initialization_task = asyncio.create_task(
        initialize_incident_service(app, settings, repository),
        name="incident-management-initialization",
    )
    logger.info("Application is listening while ServiceNow history loads in the background")
    try:
        yield
    finally:
        task: asyncio.Task[None] = app.state.initialization_task
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info("Background incident initialization was cancelled during shutdown")


async def initialize_incident_service(
    app: FastAPI, settings: Settings, repository: ServiceNowIncidentRepository
) -> None:
    """Load historical evidence without delaying the container's readiness port."""
    try:
        incidents = await asyncio.to_thread(repository.load_historical_incidents)
        logger.info("Loaded %d resolved/closed incidents from ServiceNow into the historical index", len(incidents))
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
        app.state.initialization_status = "ok"
        logger.info("Historical incident initialization completed")
    except Exception as error:
        app.state.initialization_status = "error"
        app.state.initialization_error = str(error)
        logger.exception("Historical incident initialization failed")

app = FastAPI(title="Incident Management API", version="1.0.0", lifespan=lifespan)


def service_from(request: Request) -> IncidentManagementService:
    service: IncidentManagementService | None = request.app.state.incident_service
    if service is None:
        status = request.app.state.initialization_status
        detail = request.app.state.initialization_error or "Historical incident data is still loading."
        raise HTTPException(status_code=503, detail={"status": status, "message": detail})
    return service

@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status=request.app.state.initialization_status,
        historicalIncidentCount=request.app.state.historical_incident_count,
        detail=request.app.state.initialization_error,
    )


@app.get("/api/v1/incidents/historical", response_model=list[Incident], tags=["incidents"])
async def historical_incidents(request: Request) -> list[Incident]:
    """Show resolved and closed incidents imported from ServiceNow at startup."""
    logger.info("Historical incidents endpoint requested")
    incidents = service_from(request).historical_incidents()
    logger.info("Historical incidents endpoint returned %d records", len(incidents))
    return incidents


@app.get("/api/v1/incidents/active", response_model=list[Incident], tags=["incidents"])
async def active_incidents(request: Request) -> list[Incident]:
    """Fetch the current active incidents from the configured ServiceNow instance."""
    repository: ServiceNowIncidentRepository = request.app.state.servicenow_repository
    logger.info("Active incidents endpoint requested; fetching current records from ServiceNow")
    try:
        incidents = repository.load_active_incidents()
        logger.info("Active incidents endpoint returned %d records", len(incidents))
        return incidents
    except RuntimeError as error:
        logger.warning("Active incidents endpoint could not load ServiceNow records: %s", error)
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/v1/incidents/analyze", response_model=IncidentAnalysis, tags=["incidents"])
async def analyze_incident(payload: AnalyzeRequest, request: Request) -> IncidentAnalysis:
    try:
        return await service_from(request).analyze(payload.incident, payload.limit)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
