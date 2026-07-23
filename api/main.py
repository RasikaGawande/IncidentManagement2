"""ServiceNow incident API entry point."""

from contextlib import asynccontextmanager
import asyncio
import logging
from typing import AsyncIterator, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from core.config import PROJECT_ROOT, Settings
from domain.models import Incident
from repositories.json_repository import ServiceNowFallbackRepository
from repositories.servicenow_repository import ServiceNowIncidentRepository

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings.from_environment()
    app.state.fallback_repository = ServiceNowFallbackRepository(PROJECT_ROOT / "data")
    app.state.servicenow_repository = None
    if settings.has_servicenow_credentials:
        app.state.servicenow_repository = ServiceNowIncidentRepository(
            settings.servicenow_instance_url or "",
            settings.servicenow_username or "",
            settings.servicenow_password or "",
            settings.servicenow_incident_limit,
        )
        logger.info("ServiceNow incident API is configured")
    else:
        logger.info("ServiceNow is not fully configured; incident endpoints will use fallback data")
    yield


app = FastAPI(title="ServiceNow Incident API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get(
    "/api/v1/incidents/historical",
    response_model=list[Incident],
    response_model_exclude={"updated_at"},
    tags=["incidents"],
)
async def historical_incidents(request: Request) -> list[Incident]:
    """Return resolved incidents, or local fallback records when ServiceNow is unavailable."""
    return await _load_incidents(
        request,
        "historical",
        lambda repository: repository.load_historical_incidents,
    )


@app.get(
    "/api/v1/incidents/active",
    response_model=list[Incident],
    response_model_exclude={"resolved_at"},
    tags=["incidents"],
)
async def active_incidents(request: Request) -> list[Incident]:
    """Return unresolved active incidents, or local fallback records when ServiceNow is unavailable."""
    return await _load_incidents(
        request,
        "active",
        lambda repository: repository.load_active_incidents,
    )


async def _load_incidents(
    request: Request,
    incident_type: str,
    loader_factory: Callable[[ServiceNowIncidentRepository], Callable[[], list[Incident]]],
) -> list[Incident]:
    repository: ServiceNowIncidentRepository | None = request.app.state.servicenow_repository
    if repository is not None:
        try:
            incidents = await asyncio.to_thread(loader_factory(repository))
            logger.info("Returned %d ServiceNow %s incidents", len(incidents), incident_type)
            return incidents
        except RuntimeError as error:
            logger.info(
                "ServiceNow %s request failed (%s); returning fallback incident data.",
                incident_type,
                error,
            )
    else:
        logger.info("ServiceNow is unavailable; returning fallback %s incident data.", incident_type)

    fallback_repository: ServiceNowFallbackRepository = request.app.state.fallback_repository
    try:
        loader = (
            fallback_repository.load_active_incidents
            if incident_type == "active"
            else fallback_repository.load_historical_incidents
        )
        incidents = await asyncio.to_thread(loader)
        logger.info("Returned %d fallback %s incidents", len(incidents), incident_type)
        return incidents
    except RuntimeError as error:
        logger.error("Fallback %s incident data could not be loaded: %s", incident_type, error)
        return []
