"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import asyncio
import logging
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from agents.deployment_check import DeploymentCheckAgent
from agents.code_investigation import CodeInvestigationAgent
from core.config import PROJECT_ROOT, Settings
from domain.models import AnalyzeRequest, HealthResponse, Incident, IncidentAnalysis
from repositories.json_repository import DeploymentHistoryRepository, ServiceNowFallbackRepository
from repositories.servicenow_repository import ServiceNowIncidentRepository
from repositories.code_repository import GithubCodeRepository, JsonCodeRepository
from services.advisor import IncidentAdvisor
from services.incident_management import IncidentManagementService
from services.azure_openai import AzureOpenAIClient
from vector.in_memory_store import InMemoryIncidentVectorStore

logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.incident_service = None
    app.state.historical_incident_count = 0
    app.state.initialization_error = None
    app.state.initialization_lock = asyncio.Lock()
    app.state.settings = None
    app.state.servicenow_repository = None
    app.state.servicenow_fallback_repository = ServiceNowFallbackRepository(PROJECT_ROOT / "data")
    try:
        settings = Settings.from_environment()
        if not settings.servicenow_instance_url:
            raise RuntimeError(
                "ServiceNow is required. Set SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, "
                "and SERVICENOW_PASSWORD."
            )
        app.state.settings = settings
        app.state.servicenow_fallback_repository = ServiceNowFallbackRepository(settings.data_directory)
        app.state.servicenow_repository = ServiceNowIncidentRepository(
            settings.servicenow_instance_url,
            settings.servicenow_username,
            settings.servicenow_password,
            settings.servicenow_incident_limit,
        )
        app.state.initialization_status = "ok"
        logger.info("Application started; ServiceNow history will load only when requested")
    except (RuntimeError, ValueError) as error:
        app.state.initialization_status = "error"
        app.state.initialization_error = str(error)
        logger.error("Application started without incident integrations: %s", error)
    yield


async def load_incident_service(request: Request) -> IncidentManagementService:
    """Build the analysis index only when analysis is first requested."""
    existing_service: IncidentManagementService | None = request.app.state.incident_service
    if existing_service is not None:
        return existing_service
    async with request.app.state.initialization_lock:
        existing_service = request.app.state.incident_service
        if existing_service is not None:
            return existing_service
        settings: Settings | None = request.app.state.settings
        repository: ServiceNowIncidentRepository | None = request.app.state.servicenow_repository
        if settings is None or repository is None:
            detail = request.app.state.initialization_error or "Incident integrations are not configured."
            raise HTTPException(status_code=503, detail=detail)
        request.app.state.initialization_status = "starting"
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
            service = IncidentManagementService(
                vector_store=vector_store,
                advisor=IncidentAdvisor(azure_openai),
                deployment_agent=DeploymentCheckAgent(
                    DeploymentHistoryRepository(settings.data_directory)
                ),
                code_agent=CodeInvestigationAgent(code_repository),
                similarity_threshold=settings.similarity_threshold,
            )
            request.app.state.incident_service = service
            request.app.state.historical_incident_count = vector_store.count
            request.app.state.initialization_status = "ok"
            logger.info("Historical incident initialization completed")
            return service
        except Exception as error:
            request.app.state.initialization_status = "error"
            request.app.state.initialization_error = str(error)
            logger.exception("Historical incident initialization failed")
            raise HTTPException(status_code=503, detail=str(error)) from error

app = FastAPI(title="Incident Management API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status=request.app.state.initialization_status,
        historicalIncidentCount=request.app.state.historical_incident_count,
        detail=request.app.state.initialization_error,
    )


@app.get(
    "/api/v1/incidents/historical",
    response_model=list[Incident],
    response_model_exclude={"updated_at"},
    tags=["incidents"],
)
async def historical_incidents(request: Request) -> list[Incident]:
    """Fetch the current resolved and closed incidents from ServiceNow."""
    repository: ServiceNowIncidentRepository | None = request.app.state.servicenow_repository
    if repository is None:
        detail = request.app.state.initialization_error or "ServiceNow is not configured."
        raise HTTPException(status_code=503, detail=detail)
    logger.info("Historical incidents endpoint requested; fetching records from ServiceNow")
    try:
        incidents = await asyncio.to_thread(repository.load_historical_incidents)
        logger.info("Historical incidents endpoint returned %d records", len(incidents))
        return incidents
    except RuntimeError as error:
        return await _load_servicenow_fallback(request, "historical", error)


@app.get(
    "/api/v1/incidents/active",
    response_model=list[Incident],
    response_model_exclude={"resolved_at"},
    tags=["incidents"],
)
async def active_incidents(request: Request) -> list[Incident]:
    """Fetch the current active incidents from the configured ServiceNow instance."""
    repository: ServiceNowIncidentRepository | None = request.app.state.servicenow_repository
    if repository is None:
        detail = request.app.state.initialization_error or "ServiceNow is not configured."
        raise HTTPException(status_code=503, detail=detail)
    logger.info("Active incidents endpoint requested; fetching current records from ServiceNow")
    try:
        incidents = await asyncio.to_thread(repository.load_active_incidents)
        logger.info("Active incidents endpoint returned %d records", len(incidents))
        return incidents
    except RuntimeError as error:
        return await _load_servicenow_fallback(request, "active", error)


async def _load_servicenow_fallback(
    request: Request, incident_type: str, service_now_error: RuntimeError
) -> list[Incident]:
    """Return local demo data when ServiceNow cannot be reached."""
    repository: ServiceNowFallbackRepository = request.app.state.servicenow_fallback_repository
    try:
        loader = (
            repository.load_active_incidents
            if incident_type == "active"
            else repository.load_historical_incidents
        )
        incidents = await asyncio.to_thread(loader)
    except RuntimeError as fallback_error:
        logger.error(
            "ServiceNow %s request failed (%s) and fallback data is unavailable: %s",
            incident_type,
            service_now_error,
            fallback_error,
        )
        raise HTTPException(status_code=503, detail=str(service_now_error)) from fallback_error
    logger.info(
        "ServiceNow %s request failed (%s); returning %d fallback incidents.",
        incident_type,
        service_now_error,
        len(incidents),
    )
    return incidents


@app.post("/api/v1/incidents/analyze", response_model=IncidentAnalysis, tags=["incidents"])
async def analyze_incident(payload: AnalyzeRequest, request: Request) -> IncidentAnalysis:
    try:
        service = await load_incident_service(request)
        return await service.analyze(payload.incident, payload.limit)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
