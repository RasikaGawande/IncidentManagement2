"""ServiceNow Table API adapter for resolved incident history."""

import logging
from typing import Any

import httpx

from domain.models import Incident

logger = logging.getLogger("uvicorn.error")


class ServiceNowIncidentRepository:
    """Loads resolved and closed incidents from a ServiceNow instance."""

    _FIELDS = (
        "number,short_description,description,close_notes,close_code,priority,"
        "cmdb_ci,business_service,opened_at,resolved_at"
    )

    def __init__(self, instance_url: str, username: str, password: str, limit: int = 200) -> None:
        self._instance_url = instance_url.rstrip("/")
        self._auth = (username, password)
        self._limit = limit

    def load_historical_incidents(self) -> list[Incident]:
        return self._load_incidents("active=false^ORDERBYDESCresolved_at")

    def load_active_incidents(self) -> list[Incident]:
        """Load open/in-progress incidents without adding them to historical search."""
        return self._load_incidents("active=true^ORDERBYDESCopened_at")

    def _load_incidents(self, query: str) -> list[Incident]:
        logger.info("Requesting ServiceNow incidents with query=%s and limit=%d", query, self._limit)
        try:
            response = httpx.get(
                f"{self._instance_url}/api/now/table/incident",
                auth=self._auth,
                headers={"Accept": "application/json"},
                params={
                    "sysparm_query": query,
                    "sysparm_limit": self._limit,
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                    "sysparm_fields": self._FIELDS,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            records = response.json().get("result", [])
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("ServiceNow incident request failed: %s", error)
            raise RuntimeError(f"ServiceNow incident history could not be loaded: {error}") from error
        incidents = [self._to_incident(record) for record in records]
        logger.info("ServiceNow returned %d incident records", len(incidents))
        return incidents

    @staticmethod
    def _to_incident(record: dict[str, Any]) -> Incident:
        title = _display_value(record.get("short_description")) or "ServiceNow incident"
        description = _display_value(record.get("description"))
        close_notes = _display_value(record.get("close_notes"))
        service = (
            _display_value(record.get("cmdb_ci"))
            or _display_value(record.get("business_service"))
            or "unknown-service"
        )
        return Incident(
            id=_display_value(record.get("number")) or "unknown-incident",
            title=title,
            service=service,
            severity=_severity(_display_value(record.get("priority"))),
            symptoms=description or title,
            rootCause=_display_value(record.get("close_code")) or None,
            resolution=close_notes or None,
        )


def _display_value(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("display_value") or value.get("value")
    return str(value).strip() if value else ""


def _severity(priority: str) -> str:
    """Keep ServiceNow's priority in a compact, model-friendly form."""
    first = priority.strip()[:1]
    return f"P{first}" if first.isdigit() else (priority or "P3")
